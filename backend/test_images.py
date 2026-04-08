"""
Quick test to check if images are in the knowledge base
"""
from app.db.database import get_connection

def test_images():
    conn = get_connection()
    cur = conn.cursor()
    
    # Check for IMAGE_REF markers in chunks
    cur.execute("""
        SELECT chunk_text 
        FROM kb_chunks 
        WHERE bot_id = 1 
        AND chunk_text LIKE '%IMAGE_REF%' 
        LIMIT 5
    """)
    
    results = cur.fetchall()
    
    print(f"\n✅ Found {len(results)} chunks with images\n")
    
    if results:
        for i, row in enumerate(results, 1):
            text = row[0]
            # Extract just the IMAGE_REF part
            import re
            images = re.findall(r'\[IMAGE_REF:(https?://[^\]]+)\]', text)
            print(f"Chunk {i}:")
            print(f"  Text preview: {text[:100]}...")
            print(f"  Images: {images}")
            print()
    else:
        print("❌ No images found in knowledge base")
        print("\nTo add images:")
        print("1. Upload HTML files with <img> tags")
        print("2. Upload PDF/PPTX with images")
        print("3. Upload JPG/PNG files directly")
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    test_images()
