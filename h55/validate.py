#!/usr/bin/env python3
"""
Code validation script for MotifDiscovery project.
Performs static analysis checks on C++ source files.
"""

import os
import re
import sys
from pathlib import Path

def check_file_includes(filepath):
    """Check that all required includes are present."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    filename = os.path.basename(filepath)
    
    include_pattern = r'#include\s+[<"]([^>"]+)[>"]'
    includes = re.findall(include_pattern, content)
    
    if filename == 'main.cpp':
        required = ['sequence.h', 'pwm.h', 'statistics.h', 
                   'em_algorithm.h', 'gibbs_sampler.h', 
                   'tcm_model.h', 'output_formatter.h']
        for inc in required:
            if inc not in includes:
                issues.append(f"Missing include: {inc}")
    
    ifndef_pattern = r'#ifndef\s+(\w+_H)'
    ifndef_match = re.search(ifndef_pattern, content)
    if filename.endswith('.h') and not ifndef_match:
        issues.append("Missing #ifndef header guard")
    
    if ifndef_match:
        guard = ifndef_match.group(1)
        if guard not in content:
            issues.append(f"Header guard {guard} not properly closed")
    
    return issues

def check_syntax_basics(filepath):
    """Basic syntax checks."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    issues = []
    open_braces = 0
    close_braces = 0
    open_parens = 0
    close_parens = 0
    
    for i, line in enumerate(lines, 1):
        open_braces += line.count('{')
        close_braces += line.count('}')
        open_parens += line.count('(')
        close_parens += line.count(')')
        
        if 'std::cout' in line and '<iostream>' not in ''.join(lines[:i]):
            if '#include <iostream>' not in ''.join(lines[:20]):
                pass  # Allow includes at top
        
        if line.rstrip().endswith('; ;'):
            issues.append(f"Line {i}: Double semicolon")
        
        if '\t' in line:
            issues.append(f"Line {i}: Tab character found (use spaces)")
    
    if open_braces != close_braces:
        issues.append(f"Mismatched braces: {open_braces} open, {close_braces} close")
    if open_parens != close_parens:
        issues.append(f"Mismatched parentheses: {open_parens} open, {close_parens} close")
    
    return issues

def check_namespace_usage(filepath):
    """Check for proper namespace usage."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    
    if 'using namespace std;' in content:
        issues.append("Avoid 'using namespace std;', use std:: prefix")
    
    return issues

def validate_project():
    """Validate entire project."""
    print("="*60)
    print("MotifDiscovery Project Code Validation")
    print("="*60)
    print()
    
    project_root = Path(__file__).parent
    include_dir = project_root / 'include'
    src_dir = project_root / 'src'
    
    all_issues = []
    files_checked = 0
    
    print("Checking header files...")
    for h_file in sorted(include_dir.glob('*.h')):
        print(f"  {h_file.name}...", end=' ')
        issues = []
        issues.extend(check_file_includes(str(h_file)))
        issues.extend(check_syntax_basics(str(h_file)))
        issues.extend(check_namespace_usage(str(h_file)))
        
        if issues:
            print(f"FAIL ({len(issues)} issues)")
            for issue in issues:
                print(f"    - {issue}")
                all_issues.append(f"{h_file.name}: {issue}")
        else:
            print("PASS")
        files_checked += 1
    
    print("\nChecking source files...")
    for cpp_file in sorted(src_dir.glob('*.cpp')):
        print(f"  {cpp_file.name}...", end=' ')
        issues = []
        issues.extend(check_file_includes(str(cpp_file)))
        issues.extend(check_syntax_basics(str(cpp_file)))
        issues.extend(check_namespace_usage(str(cpp_file)))
        
        if issues:
            print(f"FAIL ({len(issues)} issues)")
            for issue in issues:
                print(f"    - {issue}")
                all_issues.append(f"{cpp_file.name}: {issue}")
        else:
            print("PASS")
        files_checked += 1
    
    print("\nChecking build files...")
    build_files = ['CMakeLists.txt', 'build.bat', 'build.sh', 'example.fasta', 'README.md']
    for bf in build_files:
        bf_path = project_root / bf
        if bf_path.exists():
            print(f"  {bf}... EXISTS")
        else:
            print(f"  {bf}... MISSING")
            all_issues.append(f"Missing build file: {bf}")
    
    print("\n" + "="*60)
    print(f"Summary: {files_checked} files checked")
    print(f"         {len(all_issues)} issues found")
    print("="*60)
    
    if all_issues:
        print("\nDetailed issues:")
        for issue in all_issues:
            print(f"  - {issue}")
        return 1
    else:
        print("\nAll checks passed!")
        print("\nTo compile and run:")
        print("  1. Install MinGW: winget install BrechtSanders.WinLibs.POSIX.UCRT")
        print("  2. Restart terminal")
        print("  3. Run: build.bat")
        print("  4. Test: build\\motif_discovery.exe -i example.fasta -w 8")
        return 0

if __name__ == '__main__':
    sys.exit(validate_project())
