#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
/usr/bin/swift apps/CaptureFloater.swift
