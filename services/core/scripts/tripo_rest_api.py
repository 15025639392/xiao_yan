"""用 Tripo REST API 将图片转为 3D 模型（通过代理）"""
import base64, json, os, sys, time, re
from pathlib import Path
from email.message import EmailMessage
import urllib.request
import urllib.error

API_KEY = "tsk_VcTb_bY2f04u4iiql0vH579NcK4m8Oj_OzfxJIQ8wQO"
BASE_URL = "https://api.tripo3d.ai/v2/openapi"
IMAGE_PATH = "/Users/ldy/Desktop/work/xiao_yan/ig_05316235a269e22c0169eb9e02201081919efd020e360c3b6c.png"
OUTPUT_DIR = Path("/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output")

# Ensure proxy is set
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7890"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"
os.environ["http_proxy"] = "http://127.0.0.1:7890"
os.environ["https_proxy"] = "http://127.0.0.1:7890"


def api_request(method, path, data=None, content_type="application/json"):
    url = f"{BASE_URL}{path}"
    body = None
    if data is not None:
        if isinstance(data, bytes):
            body = data
        else:
            body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {API_KEY}")
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp_body = resp.read()
            if resp_body:
                return json.loads(resp_body)
            return {}
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"  HTTP {e.code}: {err}")
        raise


def upload_file(filepath):
    """Upload file via multipart form data"""
    print("📤 上传文件...")

    boundary = "----TripoUploadBoundary" + os.urandom(8).hex()
    filename = Path(filepath).name

    # Build multipart body manually
    body_parts = []
    body_parts.append(f"--{boundary}".encode())
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
    body_parts.append(b"Content-Type: image/png")
    body_parts.append(b"")
    with open(filepath, "rb") as f:
        body_parts.append(f.read())
    body_parts.append(f"--{boundary}--".encode())

    body = b"\r\n".join(body_parts)
    ct = f"multipart/form-data; boundary={boundary}"

    result = api_request("POST", "/upload", data=body, content_type=ct)
    token = result.get("data", {}).get("image_token")
    print(f"   文件上传成功: token={token[:16] if token else 'N/A'}...")
    return token


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Upload image
    file_token = upload_file(IMAGE_PATH)
    if not file_token:
        print("❌ 上传失败")
        sys.exit(1)

    # Step 2: Create task
    print("🚀 创建 image_to_model 任务...")
    task_data = {
        "type": "image_to_model",
        "file": {
            "type": "png",
            "file_token": file_token,
        },
        "model_version": "v3.1-20260211",
        "texture_quality": "detailed",
        "geometry_quality": "detailed",
        "pbr": True,
        "texture": True,
        "texture_alignment": "original_image",
    }
    result = api_request("POST", "/task", data=task_data)
    task_id = result.get("data", {}).get("task_id")
    if not task_id:
        print(f"❌ 未获取到 task_id: {json.dumps(result, ensure_ascii=False)}")
        sys.exit(1)
    print(f"✅ Task ID: {task_id}")

    # Step 3: Poll for completion
    print("⏳ 等待生成...")
    max_wait = 600
    start = time.time()
    while time.time() - start < max_wait:
        status_resp = api_request("GET", f"/task/{task_id}")
        data = status_resp.get("data", {})
        status = data.get("status")
        progress = data.get("progress", 0)
        elapsed = time.time() - start
        print(f"   [{elapsed:3.0f}s] status={status} progress={progress}%")

        if status == "success":
            output = data.get("output", {})
            print(f"🎉 生成成功！output keys: {list(output.keys())}")

            for model_type, url in output.items():
                if isinstance(url, str) and url.startswith("http"):
                    fname = url.split("/")[-1].split("?")[0]
                    if not fname:
                        fname = f"{model_type}.glb"
                    out_path = OUTPUT_DIR / fname
                    print(f"📥 {model_type}: {url[:80]}... → {out_path}")
                    urllib.request.urlretrieve(url, str(out_path))
                    print(f"   → {out_path} ({out_path.stat().st_size/1024:.0f} KB)")
            break
        elif status in ("failed", "error"):
            print(f"❌ 任务失败: {json.dumps(data, ensure_ascii=False, indent=2)}")
            break
        time.sleep(5)
    else:
        print("❌ 超时")


if __name__ == "__main__":
    main()
