use std::{collections::HashMap, sync::Arc};

use anyhow::{bail, Context, Result};
use pdk_crypto::{verify_event_ack, verify_heartbeat_ack};
use pdk_protocol::v1::{
    control_plane_client::ControlPlaneClient, SignedDomainEvent, SignedEventAck, SignedHeartbeat,
    SignedHeartbeatAck,
};
use pdk_transport::{client_tls, TlsFileConfig};
use tonic::transport::{Channel, Endpoint};

use crate::policy::TrustedControllerKey;

#[derive(Clone)]
pub struct ControlPlaneLink {
    channel: Channel,
    domain_id: String,
    node_id: String,
    trusted_controllers: Arc<HashMap<String, TrustedControllerKey>>,
}

impl ControlPlaneLink {
    pub fn new(
        uri: &str,
        server_name: &str,
        tls: &TlsFileConfig,
        domain_id: impl Into<String>,
        node_id: impl Into<String>,
        trusted_controllers: HashMap<String, TrustedControllerKey>,
    ) -> Result<Self> {
        let endpoint = Endpoint::from_shared(uri.to_owned())
            .context("parsing control-plane URI")?
            .tls_config(client_tls(tls, server_name)?)?;
        Ok(Self {
            channel: endpoint.connect_lazy(),
            domain_id: domain_id.into(),
            node_id: node_id.into(),
            trusted_controllers: Arc::new(trusted_controllers),
        })
    }

    pub async fn register(
        &self,
        heartbeat: SignedHeartbeat,
        boot_id: &str,
        sequence: u64,
    ) -> Result<SignedHeartbeatAck> {
        let mut client = ControlPlaneClient::new(self.channel.clone());
        let ack = client
            .register_node(heartbeat)
            .await
            .context("registering node with control plane")?
            .into_inner();
        self.verify_heartbeat_ack(&ack, boot_id, sequence)?;
        Ok(ack)
    }

    pub async fn heartbeat(
        &self,
        heartbeat: SignedHeartbeat,
        boot_id: &str,
        sequence: u64,
    ) -> Result<SignedHeartbeatAck> {
        let mut client = ControlPlaneClient::new(self.channel.clone());
        let ack = client
            .heartbeat(heartbeat)
            .await
            .context("sending node heartbeat")?
            .into_inner();
        self.verify_heartbeat_ack(&ack, boot_id, sequence)?;
        Ok(ack)
    }

    pub async fn submit_event(&self, event: SignedDomainEvent) -> Result<SignedEventAck> {
        let expected_event_id = event
            .payload
            .as_ref()
            .context("queued domain event payload missing")?
            .event_id
            .clone();
        let mut client = ControlPlaneClient::new(self.channel.clone());
        let ack = client
            .submit_event(event)
            .await
            .context("submitting buffered domain event")?
            .into_inner();
        let payload = ack.payload.as_ref().context("event ACK payload missing")?;
        if payload.domain_id != self.domain_id {
            bail!("event ACK belongs to another domain");
        }
        if payload.event_id != expected_event_id {
            bail!("event ACK does not match submitted event");
        }
        let controller = self
            .trusted_controllers
            .get(&payload.controller_id)
            .context("event ACK controller is not trusted")?;
        if ack.key_id != controller.key_id {
            bail!("event ACK key_id is not enrolled");
        }
        verify_event_ack(&ack, &controller.verifying_key)?;
        Ok(ack)
    }

    fn verify_heartbeat_ack(
        &self,
        ack: &SignedHeartbeatAck,
        boot_id: &str,
        sequence: u64,
    ) -> Result<()> {
        let payload = ack.payload.as_ref().context("heartbeat ACK payload missing")?;
        if payload.domain_id != self.domain_id {
            bail!("heartbeat ACK belongs to another domain");
        }
        if payload.node_id != self.node_id {
            bail!("heartbeat ACK targets another node");
        }
        if payload.boot_id != boot_id || payload.accepted_sequence != sequence {
            bail!("heartbeat ACK does not match the current boot and sequence");
        }
        let controller = self
            .trusted_controllers
            .get(&payload.controller_id)
            .context("heartbeat ACK controller is not trusted")?;
        if ack.key_id != controller.key_id {
            bail!("heartbeat ACK key_id is not enrolled");
        }
        verify_heartbeat_ack(ack, &controller.verifying_key)?;
        Ok(())
    }
}
