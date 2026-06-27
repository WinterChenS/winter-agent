"""Quick MinIO connectivity and upload test."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'ai_service'))

from services.minio_client import upload_image, _get_client, scan_and_upload_images

# 1. Connection test
client = _get_client()
print(f"Client: {client}")
if client:
    try:
        buckets = list(client.list_buckets())
        print(f"Buckets: {[b.name for b in buckets]}")
    except Exception as e:
        print(f"Connection ERROR: {e}")

# 2. Upload test
with tempfile.NamedTemporaryFile(suffix='.png', delete=False, mode='w') as f:
    f.write('test-png-content')
    path = f.name
url = upload_image(path)
print(f"Upload: {url}")
os.unlink(path)

# 3. Scan test (check workspace for existing PNGs)
workspace = os.path.join(os.path.dirname(__file__), '..')
pngs = [f for f in os.listdir(workspace) if f.endswith('.png')]
print(f"Workspace PNGs: {pngs}")
for png in pngs[:3]:
    url = upload_image(os.path.join(workspace, png))
    print(f"  {png} -> {url}")
