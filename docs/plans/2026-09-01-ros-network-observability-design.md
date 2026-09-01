# ROS Network Observability Design

## Goal

Give a Raspberry Pi 5 operator a small, dependency-free view of ROS 2 isolation,
graph size, suspicious discovery peers, and host network throughput from the
existing FastAPI dashboard.

## Boundary

DDNS only maps a hostname to an IP address; it does not isolate DDS discovery.
Rosy continues to isolate DDS with a per-robot `ROS_DOMAIN_ID`, a unique ROS
namespace, and a CycloneDDS profile bound to loopback. Wi-Fi clients reach the
robot through FastAPI, not DDS. The dashboard reports this policy and warns when
the observed graph contains duplicate fully-qualified node names or nodes outside
the configured namespace. Such warnings are collision indicators, not proof of a
specific remote robot.

## Architecture

`RosGraphMonitor` reads the local rclpy graph through the existing
`RosyCoreNode`. It produces a bounded, cached snapshot containing node and topic
counts, publisher/subscriber edges, configured domain and namespace, DDS
isolation mode, and explicit warnings. `HostRuntimeProbe` accepts this provider
and combines the graph with sampled `/proc/net/dev` receive/transmit rates. The
existing authenticated `/api/v1/system/runtime` endpoint remains the only API
contract that changes.

The dashboard keeps the current FastAPI-served HTML/CSS/JavaScript model. A
compact industrial network panel renders status chips, RX/TX sparklines, and an
SVG node-topic map without React, a chart library, or another service. It remains
usable when ROS graph or host counters are unavailable.

## Safety and limits

- Graph snapshots are cached for one second and capped at 64 nodes, 96 topics,
  and 256 edges.
- Only names, types, counts, rates, and non-secret configuration identifiers are
  exposed.
- The UI is read-only; it cannot change domain, namespace, DDS interfaces, or
  network settings.
- Domain assignment remains a provisioning decision. A collision warning tells
  the operator to stop motion and correct `.env`, not to mutate DDS at runtime.

## Verification

Pure tests cover domain parsing, namespace classification, duplicate nodes,
bounded edges, bandwidth deltas, and graceful degradation. Dashboard structure
tests verify that the panel, graph SVG, warnings, and runtime contract remain
present. Container configuration tests verify `/proc/net/dev` visibility.
