use std::{collections::HashMap, fs, path::Path, sync::Arc};

use anyhow::{Context, Result, bail};
use serde::Deserialize;
use sha2::{Digest, Sha256};
use tonic::{
    Request, Status,
    service::Interceptor,
    transport::{
        Certificate, ClientTlsConfig, Identity, ServerTlsConfig,
        server::{TcpConnectInfo, TlsConnectInfo},
    },
};
use x509_parser::{extensions::GeneralName, parse_x509_certificate};

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct TlsFileConfig {
    pub certificate_chain: std::path::PathBuf,
    pub private_key: std::path::PathBuf,
    pub trust_bundle: std::path::PathBuf,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PeerBindingConfig {
    pub identity: String,
    pub role: String,
    pub certificate_sha256: String,
    #[serde(default)]
    pub required_uri_san: Option<String>,
}

#[derive(Clone, Debug)]
pub struct PeerIdentity {
    pub identity: String,
    pub role: String,
    pub certificate_sha256: String,
    pub uri_sans: Vec<String>,
}

#[derive(Clone, Default)]
pub struct PeerRegistry {
    by_fingerprint: Arc<HashMap<String, PeerBindingConfig>>,
}

impl PeerRegistry {
    pub fn new(bindings: impl IntoIterator<Item = PeerBindingConfig>) -> Result<Self> {
        let mut by_fingerprint = HashMap::new();
        for mut binding in bindings {
            binding.certificate_sha256 = normalize_fingerprint(&binding.certificate_sha256)?;
            if by_fingerprint
                .insert(binding.certificate_sha256.clone(), binding)
                .is_some()
            {
                bail!("duplicate peer certificate fingerprint");
            }
        }
        Ok(Self {
            by_fingerprint: Arc::new(by_fingerprint),
        })
    }

    fn resolve(&self, certificate_der: &[u8]) -> Result<PeerIdentity> {
        let fingerprint = certificate_fingerprint(certificate_der);
        let binding = self
            .by_fingerprint
            .get(&fingerprint)
            .with_context(|| format!("certificate fingerprint {fingerprint} is not enrolled"))?;
        let uri_sans = certificate_uri_sans(certificate_der)?;
        if let Some(required) = &binding.required_uri_san {
            if !uri_sans.iter().any(|candidate| candidate == required) {
                bail!("certificate is enrolled but lacks required URI SAN {required}");
            }
        }
        Ok(PeerIdentity {
            identity: binding.identity.clone(),
            role: binding.role.clone(),
            certificate_sha256: fingerprint,
            uri_sans,
        })
    }
}

#[derive(Clone)]
pub struct CertificateIdentityInterceptor {
    registry: PeerRegistry,
    required_role: Option<String>,
}

impl CertificateIdentityInterceptor {
    pub fn new(registry: PeerRegistry) -> Self {
        Self {
            registry,
            required_role: None,
        }
    }

    pub fn requiring_role(mut self, role: impl Into<String>) -> Self {
        self.required_role = Some(role.into());
        self
    }
}

impl Interceptor for CertificateIdentityInterceptor {
    fn call(&mut self, mut request: Request<()>) -> std::result::Result<Request<()>, Status> {
        let connect_info = request
            .extensions()
            .get::<TlsConnectInfo<TcpConnectInfo>>()
            .ok_or_else(|| Status::unauthenticated("TLS connection identity is unavailable"))?;
        let certificates = connect_info
            .peer_certs()
            .ok_or_else(|| Status::unauthenticated("client certificate is required"))?;
        let leaf = certificates
            .first()
            .ok_or_else(|| Status::unauthenticated("client certificate chain is empty"))?;
        let peer = self
            .registry
            .resolve(leaf.as_ref())
            .map_err(|error| Status::permission_denied(error.to_string()))?;
        if let Some(required_role) = &self.required_role {
            if &peer.role != required_role {
                return Err(Status::permission_denied(format!(
                    "peer role {} cannot call this service; required {}",
                    peer.role, required_role
                )));
            }
        }
        request.extensions_mut().insert(peer);
        Ok(request)
    }
}

pub fn server_tls(config: &TlsFileConfig) -> Result<ServerTlsConfig> {
    enforce_private_file_permissions(&config.private_key)?;
    let certificate_chain = fs::read(&config.certificate_chain)
        .with_context(|| format!("reading {}", config.certificate_chain.display()))?;
    let private_key = fs::read(&config.private_key)
        .with_context(|| format!("reading {}", config.private_key.display()))?;
    let trust_bundle = fs::read(&config.trust_bundle)
        .with_context(|| format!("reading {}", config.trust_bundle.display()))?;
    Ok(ServerTlsConfig::new()
        .identity(Identity::from_pem(certificate_chain, private_key))
        .client_ca_root(Certificate::from_pem(trust_bundle)))
}

pub fn client_tls(config: &TlsFileConfig, server_name: &str) -> Result<ClientTlsConfig> {
    enforce_private_file_permissions(&config.private_key)?;
    let certificate_chain = fs::read(&config.certificate_chain)
        .with_context(|| format!("reading {}", config.certificate_chain.display()))?;
    let private_key = fs::read(&config.private_key)
        .with_context(|| format!("reading {}", config.private_key.display()))?;
    let trust_bundle = fs::read(&config.trust_bundle)
        .with_context(|| format!("reading {}", config.trust_bundle.display()))?;
    Ok(ClientTlsConfig::new()
        .domain_name(server_name.to_owned())
        .identity(Identity::from_pem(certificate_chain, private_key))
        .ca_certificate(Certificate::from_pem(trust_bundle)))
}

pub fn peer_identity<T>(request: &Request<T>) -> std::result::Result<&PeerIdentity, Status> {
    request
        .extensions()
        .get::<PeerIdentity>()
        .ok_or_else(|| Status::unauthenticated("authenticated peer identity missing"))
}

pub fn certificate_fingerprint(certificate_der: &[u8]) -> String {
    let digest = Sha256::digest(certificate_der);
    digest
        .iter()
        .map(|byte| format!("{byte:02x}"))
        .collect::<String>()
}

fn certificate_uri_sans(certificate_der: &[u8]) -> Result<Vec<String>> {
    let (_, certificate) = parse_x509_certificate(certificate_der)
        .map_err(|error| anyhow::anyhow!("parsing peer certificate: {error}"))?;
    let mut uris = Vec::new();
    if let Some(san) = certificate.subject_alternative_name()? {
        for name in &san.value.general_names {
            if let GeneralName::URI(uri) = name {
                uris.push((*uri).to_owned());
            }
        }
    }
    Ok(uris)
}

fn normalize_fingerprint(value: &str) -> Result<String> {
    let normalized = value
        .chars()
        .filter(|character| character.is_ascii_hexdigit())
        .flat_map(char::to_lowercase)
        .collect::<String>();
    if normalized.len() != 64 {
        bail!("SHA-256 certificate fingerprint must contain 64 hex digits");
    }
    Ok(normalized)
}

fn enforce_private_file_permissions(path: &Path) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = fs::metadata(path)
            .with_context(|| format!("stat {}", path.display()))?
            .permissions()
            .mode()
            & 0o777;
        if mode & 0o077 != 0 {
            bail!(
                "private key {} is too permissive ({mode:o}); require 0600 or stricter",
                path.display()
            );
        }
    }
    Ok(())
}
