---
title: IPC architecture
description: Design and trust boundaries for SecretSpec client and external-provider IPC
---

SecretSpec needs two local IPC boundaries with different authority and method
sets:

```text
application or SDK
        |
        | Secret Resolution Protocol
        v
SecretSpec resolver
        |
        | Secret Provider Protocol
        v
external provider endpoint ----> provider-owned service or agent
```

The protocols share the [IPC wire protocol](/reference/ipc-wire), but they are
not one API:

| Boundary | Purpose | Authority |
| --- | --- | --- |
| [Secret Resolution Protocol](/reference/resolver-protocol) | Resolve an exact declared name through a complete SecretSpec configuration | The caller receives the resolved value or a leased file |
| [Secret Provider Protocol](/reference/provider-protocol) | Implement one provider behind SecretSpec's resolver | The endpoint receives provider addresses and values, but not SecretSpec's storage or resolver internals |

The [implementation guide](/development/ipc-implementation) turns these
contracts into crates, handlers, tests, and an implementation order.

:::caution[Version compatibility]
The IPC libraries, resolver, external-provider adapter, and protocol version 1
are available starting with SecretSpec 0.20.
:::

## Decision

The canonical interface is the wire specification. SecretSpec ships two
first-class implementations:

- `libsecretspec-ipc`, a portable C11 client library distributed as source plus
  static and shared libraries. It is C, not a C ABI over Rust.
- `secretspec-ipc`, a Rust client/server crate with typed resolution and provider
  handlers.

Nix and non-Rust resolver-mode SDKs use the C client. Rust consumers, the
SecretSpec external-provider adapter, the resolver, and Rust provider endpoints
use the Rust implementation. Both implementations are tested against the same
language-neutral conformance suite and differential state-machine tests.

The initial transport is a child process over inherited stdin and stdout on
Linux, macOS, and Windows. Messages are JSON-RPC 2.0 objects inside bounded
length-prefixed frames. A later Unix-domain socket or Windows named-pipe
transport may carry the same messages after separately specifying endpoint
authentication and discovery.

### Why C and Rust implementations?

A shared C client avoids duplicating the security-sensitive state machine across
non-Rust SDKs. C11 gives native consumers one stable ABI without imposing a Rust
toolchain or Rust static-link closure. The library uses opaque handles,
explicit-length buffers, and no callbacks into foreign runtimes, so C++, Go,
Swift, Python, and other bindings can wrap it. A native Rust implementation
avoids routing SecretSpec's own async handlers through FFI and gives Rust
consumers typed APIs.

Neither implementation is the protocol. Independent or constrained clients may
implement the canonical wire contract directly, but every implementation must
pass the same conformance suite. The C and Rust implementations additionally
run differential tests so a shared bug is less likely to redefine the contract.

The intended deliverables are therefore:

- `libsecretspec-ipc`: the pure-C client, process launcher, frame codec, JSON-RPC
  session, and public C header, with no Rust or provider dependencies;
- `secretspec-ipc`: Rust wire types, client, server dispatcher, process
  lifecycle, and typed resolution/provider handlers;
- thin non-Rust SDK bindings around the C ABI for resolver mode;
- one language-neutral conformance suite plus C/Rust differential tests.

The existing `libsecretspec` remains the embedded resolver ABI used by current
language SDKs. It is not silently changed into an IPC client. An SDK may later
offer `embedded` and `resolver` backends behind the same language-level API.

### Why not Varlink?

[Varlink](https://varlink.org/) supplies an interface language, local service
discovery conventions, framing, typed errors, streaming replies, and runtime
introspection. The maintained [zlink](https://docs.rs/zlink/0.7.0/zlink/)
implementation also provides async Rust clients and services, code generation,
and Tokio and smol integrations. SecretSpec does not use it for four reasons:

- **No multiplexing.** Varlink pipelines calls in order but has no request IDs.
  One blocked call delays later replies and cannot be cancelled independently.
  A pool of connections avoids this, but adds channel scheduling, descriptor
  limits, and replacement after cancellation.
- **Portability.** Version 1 requires private stdio sessions on Linux, macOS,
  and Windows plus a pure-C client. zlink is Rust-only and its ready-made
  transport is Unix-domain sockets. Passing anonymous sockets is a
  transport-specific zlink extension, not standard Varlink, and Windows would
  need a separate handle-transfer design.
- **Missing lifecycle semantics.** SecretSpec would still have to define
  version and capability negotiation, deadlines, cancellation, message bounds,
  leases, shutdown, and the trust model.
- **No net simplification.** Named sockets require authentication, permissions,
  discovery, and stale-socket cleanup. Connection pools replace the current
  request-ID table with another security-sensitive state machine.

See Varlink's documentation on
[ordered connections](https://varlink.org/FAQ.html#why-are-there-no-sequence-numbers-in-calls-and-replies)
and [transport-specific file descriptors](https://varlink.org/FAQ.html#can-i-transmit-file-descriptors).

[JSON-RPC 2.0](https://www.jsonrpc.org/specification) gives SecretSpec stable
request correlation, method names, results, and errors while leaving transport
and application semantics explicit. The missing stream framing and
cancellation rules are small enough to specify here and implement without a
large runtime.

This is a portability and dependency decision, not a claim that Varlink is a
bad protocol. Varlink improves interface description and generated Rust APIs,
but does not simplify SecretSpec's required lifecycle. A Unix Varlink adapter
could still be added later without changing the canonical application methods.

## Layer ownership

The layers are independently owned and versioned:

1. The wire layer owns frames, JSON-RPC envelopes, initialization, request
   IDs, deadlines, cancellation, shutdown, common errors, and resource bounds.
2. `secretspec.resolver/1` owns resolver configuration, exact-name resolution,
   value/file representations, and file leases.
3. `secretspec.provider/1` owns provider discovery, provider metadata,
   canonical addresses, provider operations, and provider error mapping.
4. A provider owns its storage, encryption, synchronization, hardware keys,
   grants, and any protocol used behind its endpoint.

An external provider exposes only the SecretSpec endpoint contract. Its
storage engine, encryption, synchronization, hardware keys, and grants stay
behind that endpoint and are never modeled in SecretSpec IPC. In-tree providers
may instead call a provider-owned Rust client directly; the compiled
`factorseal` provider uses that path.

Application methods from the two protocols must never be mixed on one
connection. Initialization selects exactly one protocol name and major
version.

## Process and transport model

Version 1 has one mandatory transport: a directly launched child with a private
stdin/stdout pair. This choice has the same security shape on all target
platforms:

- no global endpoint name is discoverable or connectable by another process;
- possession of the inherited pipe handles is the session authority;
- readiness is the successful `rpc.initialize` response;
- EOF, `rpc.shutdown`, or child exit ends the session and releases every
  session resource;
- executables are launched directly, never through a shell;
- secrets are sent only in framed requests and responses, never in command-line
  arguments.

The launcher owns environment inheritance policy. Interactive SDK use may
inherit the caller environment because providers currently use ambient
credentials. Privileged integrations should construct an allowlisted
environment. Protocol fields must not also be mirrored into environment
variables.

A persistent service transport is intentionally not version 1. It requires a
separate specification for owner-only endpoint permissions, peer credentials,
endpoint selection, stale endpoint cleanup, multi-client fairness, and
platform-specific identity. Merely finding a socket or pipe is not
authorization.

## Principal and delegation decision

For protocol version 1, an external provider endpoint acts as its own
application principal when it connects to a provider-owned agent. This rule
does not apply to compiled providers: the SecretSpec CLI or embedding
application is the process that connects to the Factorseal agent and is
therefore its authenticated principal.

The endpoint must not authorize an original application identity copied from a
JSON field. A process path, PID, `application_id`, user name, or similar value
forwarded by the resolver is only an assertion and is not authenticated
delegation.

If grants must instead follow the application that invoked SecretSpec, a later
capability must define a cryptographic delegation that is:

- issued from an identity authenticated on the client-to-resolver transport;
- signed by an issuer trusted by the provider or provider-owned agent;
- audience-bound to that provider endpoint or agent;
- scoped to operations and addresses;
- short-lived and bound to a nonce or request;
- resistant to replay, substitution, and downgrade.

Version 1 contains no caller-identity field and no delegation capability.
Adding unverified identity metadata before that design exists would create a
confused-deputy boundary.

## Compatibility rules

- Wire and application protocol versions are integers. A breaking change uses
  a new integer version.
- Optional behavior is introduced through named capabilities. A sender must
  not use a method or field gated by a capability the server did not
  advertise.
- Unknown capabilities are ignored. Unknown methods receive
  `method_not_found`. Unknown parameters are rejected so misspellings do not
  weaken a security decision.
- The C library/ABI, an SDK package, the Rust handler crate, resolver binary, and
  provider endpoint each have their own product versions. None of those version
  strings replaces protocol negotiation.
- No request that might have reached a handler is automatically replayed after
  a disconnect. A new connection is a new session.

## Non-goals for version 1

- Remote network RPC, TLS, or service-to-service authentication.
- Client-to-daemon or client-to-remote-store forwarding of secret authority.
- Exposing provider storage, caches, encryption, databases, or synchronization
  engines through the resolution protocol.
- Replacing all existing embedded language SDKs.
- Arbitrary whole-profile or arbitrary-provider access for consumers that ask
  for one declared name.
- Authenticated delegation of the original application identity.
- Exactly-once execution of provider side effects. The contract guarantees one
  terminal response, not transactional rollback after cancellation or a lost
  connection.
