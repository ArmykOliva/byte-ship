#This snippet shows and example how to use the Cohere Embed V3 models for semantic search.
# Make sure to have the Cohere SDK in at least v4.30 install: pip install -U cohere 
# Get your API key from: www.cohere.com
import cohere
import numpy as np
import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings


cohere_ef  = embedding_functions.CohereEmbeddingFunction(
        api_key="nSOmyV5kOXywsg83sjrD4FpZ453SwfL0UAkuCpUr", 
        model_name="embed-english-v3.0")

with open("data/test_log1.out","r",encoding="utf-8") as f:
  ff = f.readlines()

lines = ff[2000:3000]
ids = []
metadatas = []
for i,line in enumerate(lines):
    ids.append(str(i))
    metadatas.append({"category":"error"})

client = chromadb.PersistentClient(path="db")

collection = client.get_or_create_collection(name="Students",embedding_function=cohere_ef)
if (collection.count() == 0):
    print("Collection no")
    collection.add(
        documents = lines,
        metadatas = metadatas,
        ids = ids
    )

results = collection.query(
    query_texts=["ssh error"],
    n_results=2
)

print(results)