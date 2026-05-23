from concurrent import futures
from contextlib import asynccontextmanager
import logging
import threading

import grpc
from fastapi import FastAPI, HTTPException

import catalog_pb2
import catalog_pb2_grpc


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Simulated product database (in production this would be a real DB)
PRODUCTS = {
    "id-1": {"name": "Laptop", "stock": 10, "price": 1500.0},
    "id-2": {"name": "Mouse", "stock": 50, "price": 25.0},
    "id-3": {"name": "Keyboard", "stock": 20, "price": 45.0},
    "id-4": {"name": "Monitor", "stock": 5, "price": 300.0},
}


class CatalogGrpcService(catalog_pb2_grpc.CatalogServicer):
    def CheckStock(self, request, context):
        logger.info(f"Received CheckStock request for SKU: {request.sku}, Quantity: {request.quantity}")
        product = PRODUCTS.get(request.sku)

        if product is None:
            return catalog_pb2.StockResponse(
                sku=request.sku,
                product_name="",
                stock=0,
                price=0.0,
                available=False,
            )

        return catalog_pb2.StockResponse(
            sku=request.sku,
            product_name=product["name"],
            stock=product["stock"],
            price=product["price"],
            available=product["stock"] >= request.quantity,
        )


def run_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    catalog_pb2_grpc.add_CatalogServicer_to_server(CatalogGrpcService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Catalog gRPC server running on port 50051", flush=True)
    server.wait_for_termination()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: launch gRPC server in a background daemon thread.
    # daemon=True ensures the thread stops when the main process exits.
    thread = threading.Thread(target=run_grpc_server, daemon=True)
    thread.start()
    yield
    # Shutdown handled automatically (daemon thread terminates with process)


app = FastAPI(title="Catalog Service", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "catalog"}


@app.get("/products/{sku}")
def get_product(sku: str):
    product = PRODUCTS.get(sku)

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "sku": sku,
        "name": product["name"],
        "stock": product["stock"],
        "price": product["price"],
        "available": product["stock"] > 0,
    }
