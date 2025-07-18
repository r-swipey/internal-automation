#!/usr/bin/env python3
"""
Test Runner Script for Internal Automation System
Provides different test execution strategies for different scenarios
"""

import subprocess
import sys
import os
from datetime import datetime

def run_command(command, description):
    """Run a command and capture output"""
    print(f"\n{'='*60}")
    print(f"🔍 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False

def quick_test():
    """Run quick tests for development"""
    print("🚀 Running Quick Development Tests...")
    return run_command("python test_document.py", "Quick functionality tests")

def comprehensive_test():
    """Run comprehensive tests with full verification"""
    print("🎯 Running Comprehensive Tests...")
    return run_command("python test_comprehensive.py", "Full system verification")

def pre_deployment_test():
    """Run pre-deployment test suite"""
    print("🚨 Running Pre-Deployment Test Suite...")
    
    # Check if server is running
    server_check = run_command("curl -s http://localhost:5000/health || echo 'Server not running'", "Server health check")
    
    if not server_check:
        print("\n⚠️  WARNING: Server might not be running on localhost:5000")
        print("   Make sure to start the Flask app before running tests")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return False
    
    # Run comprehensive tests
    success = comprehensive_test()
    
    if success:
        print("\n✅ PRE-DEPLOYMENT TESTS PASSED")
        print("   System is ready for deployment!")
        return True
    else:
        print("\n❌ PRE-DEPLOYMENT TESTS FAILED")
        print("   Do NOT deploy until all tests pass!")
        return False

def post_deployment_test():
    """Run post-deployment verification"""
    print("📡 Running Post-Deployment Verification...")
    
    # These would typically run against production/staging environment
    print("⚠️  Note: Update base_url in test files for production environment")
    return comprehensive_test()

def main():
    """Main test runner"""
    print("🧪 Internal Automation Test Runner")
    print(f"⏰ Test run started at: {datetime.now()}")
    
    if len(sys.argv) < 2:
        print("\nUsage: python test_runner.py <test_type>")
        print("\nAvailable test types:")
        print("  quick        - Quick development tests")
        print("  comprehensive - Full system verification")
        print("  pre-deploy   - Pre-deployment test suite")
        print("  post-deploy  - Post-deployment verification")
        print("  zapier       - Zapier webhook tests only")
        print("  ocr          - OCR processing tests only")
        print("  workflow     - Complete workflow tests only")
        sys.exit(1)
    
    test_type = sys.argv[1].lower()
    
    if test_type == "quick":
        success = quick_test()
    elif test_type == "comprehensive":
        success = comprehensive_test()
    elif test_type == "pre-deploy":
        success = pre_deployment_test()
    elif test_type == "post-deploy":
        success = post_deployment_test()
    elif test_type == "zapier":
        success = run_command("python test_comprehensive.py zapier", "Zapier webhook tests")
    elif test_type == "ocr":
        success = run_command("python test_comprehensive.py ocr", "OCR processing tests")
    elif test_type == "workflow":
        success = run_command("python test_comprehensive.py workflow", "Complete workflow tests")
    else:
        print(f"❌ Unknown test type: {test_type}")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print(f"📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"⏰ Test run completed at: {datetime.now()}")
    
    if success:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()