import os
import sys
import json
import urllib.request

def publish_story(token, publish_status="draft", file_path=None):
    # Step 1: Get User ID
    req = urllib.request.Request("https://api.medium.com/v1/me")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(req) as response:
            res = json.loads(response.read().decode())
            user_id = res["data"]["id"]
            username = res["data"]["username"]
            print(f"✅ Authenticated as Medium User: @{username} (ID: {user_id})")
    except Exception as e:
        print(f"❌ Failed to authenticate with Medium API: {e}")
        return

    # Step 2: Read Blog File
    if not file_path:
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "building-resy-mcp-server-cloud-run.md")
        if not os.path.exists(file_path):
            file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "securing-google-cloud-environment.md")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract title from the first H1 header
    title = "Technical Guide"
    for line in content.splitlines():
        if line.startswith("# "):
            title = line.replace("# ", "").strip()
            break

    # Determine appropriate tags
    tags = ["GoogleCloud", "Python", "ArtificialIntelligence", "MachineLearning", "DeepLearning"]
    if "mcp" in file_path.lower():
        tags = ["GoogleCloud", "Python", "ArtificialIntelligence", "CloudRun", "MCP"]
    elif "slm" in file_path.lower():
        tags = ["ArtificialIntelligence", "MachineLearning", "GoogleCloud", "Python", "DeepLearning"]
    elif "securing" in file_path.lower():
        tags = ["GoogleCloud", "CyberSecurity", "CloudSecurity", "DevOps", "Governance"]

    # Step 3: Create Post Payload
    post_data = {
        "title": title,
        "contentFormat": "markdown",
        "content": content,
        "publishStatus": publish_status,  # "draft" or "public"
        "tags": tags
    }

    post_url = f"https://api.medium.com/v1/users/{user_id}/posts"
    post_req = urllib.request.Request(post_url, data=json.dumps(post_data).encode("utf-8"))
    post_req.add_header("Authorization", f"Bearer {token}")
    post_req.add_header("Content-Type", "application/json")
    post_req.add_header("Accept", "application/json")

    try:
        with urllib.request.urlopen(post_req) as response:
            post_res = json.loads(response.read().decode())
            story_url = post_res["data"]["url"]
            print(f"🎉 Successfully created {publish_status} story on Medium!")
            print(f"🔗 Story Link: {story_url}")
    except Exception as e:
        print(f"❌ Failed to publish post to Medium: {e}")

if __name__ == "__main__":
    token = os.environ.get("MEDIUM_INTEGRATION_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else None)
    if not token:
        print("Usage: python publish_to_medium.py <YOUR_MEDIUM_INTEGRATION_TOKEN> [draft|public] [file_path]")
        sys.exit(1)
    
    status = sys.argv[2] if len(sys.argv) > 2 else "draft"
    target_file = sys.argv[3] if len(sys.argv) > 3 else None
    publish_story(token, publish_status=status, file_path=target_file)

