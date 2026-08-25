"""
Launch a Serverless GPU Training Job for your SLM on Google Cloud Vertex AI.
"""

import os
import argparse
from google.cloud import aiplatform

def launch_vertex_training_job(
    project_id: str,
    region: str = "us-central1",
    staging_bucket: str = "gs://your-slm-bucket",
    display_name: str = "slm-from-scratch-training",
    epochs: int = 100,
    machine_type: str = "g2-standard-4",   # 4 vCPUs, 16GB RAM, 1x NVIDIA L4 GPU
    accelerator_type: str = "NVIDIA_L4",
    accelerator_count: int = 1
):
    print(f"🌟 Initializing Vertex AI SDK for Project: {project_id} in {region}")
    aiplatform.init(project=project_id, location=region, staging_bucket=staging_bucket)

    # 1. Define the Custom Training Job
    # We use Google Cloud's pre-built PyTorch GPU training container
    job = aiplatform.CustomTrainingJob(
        display_name=display_name,
        script_path="../train.py",
        container_uri="us-docker.pkg.dev/vertex-ai/training/pytorch-gpu.2-1.py310:latest",
        requirements=["torch", "pydantic"]
    )

    # 2. Run the training job on Vertex AI
    print(f"🚀 Submitting Custom Training Job to Vertex AI on {machine_type} with {accelerator_count}x {accelerator_type}...")
    
    gcs_output_dir = f"{staging_bucket}/models/{display_name}"
    gcs_data_path = f"{staging_bucket}/data/sample_data.txt"

    model = job.run(
        model_display_name="custom-slm-model",
        args=[
            f"--data_path={gcs_data_path}",
            f"--output_dir={gcs_output_dir}",
            f"--epochs={epochs}",
            "--batch_size=32",
            "--lr=2e-3",
            "--context_length=128",
            "--d_model=256",
            "--num_heads=8",
            "--num_layers=6"
        ],
        replica_count=1,
        machine_type=machine_type,
        accelerator_type=accelerator_type,
        accelerator_count=accelerator_count,
        sync=True
    )

    print(f"✅ Training complete! Model artifacts saved to: {gcs_output_dir}")
    return model

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Submit SLM training job to GCP Vertex AI")
    parser.add_argument("--project_id", type=str, required=True, help="Google Cloud Project ID")
    parser.add_argument("--staging_bucket", type=str, required=True, help="GCS bucket URI (e.g., gs://my-bucket)")
    parser.add_argument("--region", type=str, default="us-central1", help="GCP region")
    parser.add_argument("--epochs", type=int, default=100, help="Number of training epochs")
    
    args = parser.parse_args()
    launch_vertex_training_job(
        project_id=args.project_id,
        region=args.region,
        staging_bucket=args.staging_bucket,
        epochs=args.epochs
    )
