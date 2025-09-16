#!/usr/bin/env python3
"""Offline Kubernetes Manifest Validation.

This script validates Kubernetes manifests without requiring cluster connectivity.
Performs YAML syntax validation and Kubernetes resource structure validation.
"""

import os
import sys
from pathlib import Path

import yaml


def validate_yaml_file(file_path):
    """Validate YAML syntax and basic structure."""
    try:
        with open(file_path, "r") as f:
            docs = list(yaml.safe_load_all(f))

        valid_docs = 0
        for doc in docs:
            if doc is None:
                continue

            # Check for basic Kubernetes structure
            if isinstance(doc, dict):
                if "apiVersion" in doc and "kind" in doc:
                    valid_docs += 1
                else:
                    print(f"  ⚠️ Missing apiVersion/kind in document")

        return valid_docs > 0, len(docs), valid_docs

    except yaml.YAMLError as e:
        return False, 0, 0
    except Exception as e:
        return False, 0, 0


def validate_k8s_manifests_offline():
    """Validate all Kubernetes manifests offline."""
    print("📋 Offline Kubernetes Manifest Validation\n")

    manifest_files = [
        "k8s/namespace/namespace.yaml",
        "k8s/configmaps/app-config.yaml",
        "k8s/secrets/app-secrets-template.yaml",
        "k8s/deployments/api.yaml",
        "k8s/deployments/dashboard.yaml",
        "k8s/deployments/worker.yaml",
        "k8s/deployments/redis.yaml",
        "k8s/deployments/rabbitmq.yaml",
        "k8s/services/api-service.yaml",
        "k8s/services/dashboard-service.yaml",
        "k8s/services/redis-service.yaml",
        "k8s/services/rabbitmq-service.yaml",
        "k8s/ingress/ingress.yaml",
    ]

    valid_files = 0
    total_files = 0
    total_docs = 0
    valid_docs = 0

    for manifest in manifest_files:
        if os.path.exists(manifest):
            total_files += 1
            is_valid, doc_count, valid_doc_count = validate_yaml_file(manifest)

            if is_valid:
                print(f"✅ {manifest} - {valid_doc_count}/{doc_count} documents")
                valid_files += 1
                total_docs += doc_count
                valid_docs += valid_doc_count
            else:
                print(f"❌ {manifest} - YAML syntax error")
        else:
            print(f"⚠️ {manifest} - File not found")

    print(f"\n📊 Summary:")
    print(f"  • Files validated: {valid_files}/{total_files}")
    print(f"  • Documents validated: {valid_docs}/{total_docs}")
    print(f"  • Success rate: {valid_files/total_files*100:.1f}%")

    return valid_files == total_files


if __name__ == "__main__":
    success = validate_k8s_manifests_offline()

    print(f"\n✅ YAML Validation: {'PASSED' if success else 'FAILED'}")
    print("💡 Note: Online cluster validation requires Kubernetes connectivity")

    sys.exit(0 if success else 1)
