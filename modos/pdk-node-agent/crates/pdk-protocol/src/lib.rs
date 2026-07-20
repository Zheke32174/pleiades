//! Generated canonical PDK v1 protobuf contracts plus protocol constants.

pub mod v1 {
    tonic::include_proto!("pleiades.pdk.v1");
}

pub const PROTOCOL_VERSION: u32 = 1;
pub const HEARTBEAT_SIGNATURE_CONTEXT: &[u8] = b"PLEIADES-PDK-HEARTBEAT-V1\0";
pub const HEARTBEAT_ACK_SIGNATURE_CONTEXT: &[u8] = b"PLEIADES-PDK-HEARTBEAT-ACK-V1\0";
pub const CAPABILITY_SIGNATURE_CONTEXT: &[u8] = b"PLEIADES-PDK-CAPABILITY-V1\0";
pub const DOMAIN_EVENT_SIGNATURE_CONTEXT: &[u8] = b"PLEIADES-PDK-DOMAIN-EVENT-V1\0";
pub const EVENT_ACK_SIGNATURE_CONTEXT: &[u8] = b"PLEIADES-PDK-EVENT-ACK-V1\0";
