---
name: agent-human-trainer
description: >-
  Huấn luyện, chấm điểm hành vi 5 chiều (D1..D5 = 100 điểm), kiểm toán 8 phân lớp mâu thuẫn đặc tả (SPEC_CLASS_01..08),
  chặn lỗi AST thế hệ 5 (Gen-5 AST Patch Guard) và xuất tập dữ liệu DPO/SFT chuẩn Senior Human Engineer (TIER_5)
  trên toàn cục cho Antigravity và các mô hình LLM/Coding Agent.
---

# Agent Human Trainer — Global Senior Engineer Alignment Skill (`v1.0.0`)

Sử dụng skill này ở bất kỳ dự án nào khi cần:
1. Kiểm tra một Issue, Prompt hoặc bình luận Code Review xem có chứa mâu thuẫn kỹ thuật hay bẫy đặc tả (`SPEC_CLASS_01`..`08`) không.
2. Kiểm định bản vá mã nguồn (`audit_patch_ast_integrity`) để đảm bảo không làm hỏng cây cú pháp AST, không xóa nhầm `import unittest`/`pytest` và không làm rỗng hàm.
3. Chấm điểm chất lượng đầu ra của Agent theo thang 100 điểm (`D1`..`D5`) để đạt chuẩn `TIER_5_SENIOR_HUMAN_ENGINEER` (`>= 85/100`).
4. Xuất tập dữ liệu huấn luyện `DPO` (`dpo_senior_engineer_alignment.jsonl`) và `SFT` (`sft_senior_engineer_instruct.jsonl`) cho HuggingFace `trl`, `Unsloth`, `LLaMA-Factory` hoặc `Axolotl`.

## 1. Gọi Nhanh Trong Python (Đã Cài Đặt Toàn Cục)

```python
from agent_human_trainer import (
    audit_issue_specification,
    audit_patch_ast_integrity,
    verify_human_grade_output,
    export_all_training_artifacts,
    audit_public_community_cleanliness,
)

# 1. Kiểm toán đặc tả Issue / Review trước khi viết code
spec = audit_issue_specification(issue_title="...", issue_body="...")

# 2. Kiểm toán AST của bản vá trước khi commit
ast_check = audit_patch_ast_integrity(
    original_source=old_code,
    proposed_source=new_code,
    is_test_file=True,
)

# 3. Chấm điểm toàn diện đầu ra chuẩn Senior Human Engineer (D1..D5)
verdict = verify_human_grade_output(
    issue_text=issue_body,
    agent_response=pr_description_or_comment,
    patch_stats={"files_changed": 2, "tests_added": 2, "unrequested_files_touched": 0},
)
```

## 2. Lệnh CLI Toàn Cục

```bash
# Chạy kiểm định chuẩn (Benchmark 13 cặp chuẩn + 32 mẫu thực nghiệm) & kiểm tra độ sạch 0% rò rỉ:
python -m agent_human_trainer --export-datasets --audit-cleanliness --benchmark

# Kiểm tra trực tiếp một đề bài / bình luận Review:
python -m agent_human_trainer --audit-spec --issue-title "Title" --issue-text "Body..."
```

## 3. Đường Dẫn Mã Nguồn & Kho Công Khai
- **Gói cài đặt toàn cục trên máy**: `pip install -e . (agent-human-trainer)`
- **Kho mã nguồn mở công khai (MIT License)**: `https://github.com/khoap1220-hue/agent-human-trainer`
