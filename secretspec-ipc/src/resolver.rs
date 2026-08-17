use crate::error::{ErrorKind, RpcError};
use crate::protocol::RESOLVER_PROTOCOL;
use crate::protocol::resolver::{
    CAPABILITIES, GetParams, GetResult, InitializeApplication, InitializedApplication,
    ReleaseParams, ReleaseResult, method,
};
use crate::server::{ApplicationHandler, RequestContext, RpcResult, ServerConfig};
use async_trait::async_trait;
use serde::de::DeserializeOwned;
use serde_json::Value;
use std::sync::Arc;

/// Typed northbound handler. Implementations never parse JSON-RPC envelopes or
/// arbitrate cancellation/terminal races.
#[async_trait]
pub trait ResolverHandler: Send + Sync + 'static {
    async fn initialize(
        &self,
        context: &RequestContext,
        application: InitializeApplication,
    ) -> RpcResult<InitializedApplication>;

    async fn get(&self, context: RequestContext, params: GetParams) -> RpcResult<GetResult>;

    async fn release(
        &self,
        context: RequestContext,
        params: ReleaseParams,
    ) -> RpcResult<ReleaseResult>;

    async fn request_finished(&self, _request_id: crate::RequestId, _committed: bool) {}

    async fn shutdown(&self) {}
}

struct ResolverApplication<H> {
    handler: Arc<H>,
}

impl<H> ResolverApplication<H> {
    fn new(handler: Arc<H>) -> Self {
        Self { handler }
    }
}

#[async_trait]
impl<H: ResolverHandler> ApplicationHandler for ResolverApplication<H> {
    fn protocol(&self) -> &'static str {
        RESOLVER_PROTOCOL
    }

    fn capabilities(&self) -> Vec<String> {
        CAPABILITIES
            .iter()
            .map(|item| (*item).to_string())
            .collect()
    }

    // No `validate_capabilities` override: the hook receives this handler's own
    // `capabilities()`, which is the fixed `CAPABILITIES` constant, so checking
    // it for `resolver.get`/`resolver.release` could never fail. The provider
    // adapter does override it, because a `ProviderHandler` supplies an
    // arbitrary list whose dependency rules are worth enforcing.

    async fn initialize(&self, context: &RequestContext, application: Value) -> RpcResult<Value> {
        let application: InitializeApplication = parse(application)?;
        application.validate().map_err(invalid_params)?;
        let initialized = self.handler.initialize(context, application).await?;
        initialized
            .validate()
            .map_err(|_| RpcError::new(ErrorKind::OperationFailed))?;
        serde_json::to_value(initialized).map_err(|_| RpcError::new(ErrorKind::Internal))
    }

    async fn call(&self, context: RequestContext, method: &str, params: Value) -> RpcResult<Value> {
        match method {
            method::GET => {
                let params: GetParams = parse(params)?;
                params.validate().map_err(invalid_params)?;
                let result = self.handler.get(context, params).await?;
                serde_json::to_value(result).map_err(|_| RpcError::new(ErrorKind::Internal))
            }
            method::RELEASE => {
                let params: ReleaseParams = parse(params)?;
                params.validate().map_err(invalid_params)?;
                let result = self.handler.release(context, params).await?;
                serde_json::to_value(result).map_err(|_| RpcError::new(ErrorKind::Internal))
            }
            _ => Err(RpcError::new(ErrorKind::MethodNotFound)),
        }
    }

    async fn request_finished(&self, request_id: crate::RequestId, committed: bool) {
        self.handler.request_finished(request_id, committed).await;
    }

    async fn shutdown(&self) {
        self.handler.shutdown().await;
    }
}

fn parse<T: DeserializeOwned>(value: Value) -> RpcResult<T> {
    serde_json::from_value(value).map_err(|_| RpcError::new(ErrorKind::InvalidParams))
}

fn invalid_params(_: crate::Error) -> RpcError {
    RpcError::new(ErrorKind::InvalidParams)
}

/// Serve one typed resolution endpoint without assembling the generic adapter.
pub async fn serve_resolver<R, W, H>(
    reader: R,
    writer: W,
    handler: H,
    config: ServerConfig,
) -> crate::Result<()>
where
    R: tokio::io::AsyncRead + Unpin + Send + 'static,
    W: tokio::io::AsyncWrite + Unpin + Send + 'static,
    H: ResolverHandler,
{
    crate::server::serve(
        reader,
        writer,
        Arc::new(ResolverApplication::new(Arc::new(handler))),
        config,
    )
    .await
}
