import os
import sys
from dotenv import load_dotenv

load_dotenv('backend/.env')
load_dotenv('.env')

key = os.getenv('COHERE_API_KEY')
print(f"COHERE_API_KEY_PRESENT: {bool(key and len(key) > 5)}")
if key:
    print(f"COHERE_API_KEY_PREFIX: {key[:7]}...")

from qdrant_client import QdrantClient

# Check snapshot database
snapshot_path = os.path.abspath('artifacts/diagnostics/zto_retrieval_test/qdrant_snapshot')
client = QdrantClient(path=snapshot_path)
info = client.get_collection('cuad_train')
print(f"QDRANT_COLLECTION: cuad_train")
print(f"VECTOR_DIMENSION: {info.config.params.vectors.size}")
print(f"DISTANCE_METRIC: {info.config.params.vectors.distance}")
print(f"TOTAL_POINTS: {info.points_count}")
