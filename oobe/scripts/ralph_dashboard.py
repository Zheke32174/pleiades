#!/usr/bin/env python3
# Developing Mind — ralph_dashboard.py
# Role: Dashboard for tracking the Ralph Loop's state without interfering with it.
# Arxiv Anchor: 2604.24579 (Prop 1: Analytic Reliability) - Observability

import json
import os
import time

STATE_FILE = "./.gemini/ralph/state.json"

def print_dashboard():
    print("=== Ralph Background Loop Status ===")
    if not os.path.exists(STATE_FILE):
        print("Status: Inactive (State file not found)")
        return
        
    try:
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            
        print(f"Active: {state.get('active', False)}")
        print(f"Iteration: {state.get('current_iteration', 0)} / {state.get('max_iterations', 'inf')}")
        print(f"Started At: {state.get('started_at', 'Unknown')}")
        promise = state.get('completion_promise')
        if promise:
            print(f"Completion Promise: {promise}")
    except Exception as e:
        print(f"Error reading state: {e}")

if __name__ == "__main__":
    print_dashboard()
