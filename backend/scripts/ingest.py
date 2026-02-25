import os
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from pgvector.psycopg2 import register_vector
from app.db.database import get_connection

# 1. Models Setup
print("⏳ Loading Embedding Model...")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# 2. File Loading
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
file_name = "questions_answer.txt"
file_path = os.path.join(BASE_DIR, file_name)

if not os.path.exists(file_path):
    print(f"❌ Error: '{file_name}' not found!")
    exit()

loader = TextLoader(file_path)
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)

chunks = text_splitter.split_documents(docs)
print(f"📖 File loaded. {len(chunks)} chunks ready.")

# 3. Insert into DB
try:
    conn = get_connection()
    register_vector(conn)
    cur = conn.cursor()

    print("🚀 Inserting into 'kb_chunks' table...")

    for chunk in chunks:
        vector = embeddings.embed_query(chunk.page_content)

        cur.execute(
            "INSERT INTO kb_chunks (chunk_text, embedding) VALUES (%s, %s)",
            (chunk.page_content, vector)
        )

    conn.commit()
    cur.close()
    conn.close()

    print("✅ Data pushed to kb_chunks table.")

except Exception as e:
    print(f"❌ Database Error: {e}")