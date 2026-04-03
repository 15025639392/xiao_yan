# 目标链系统 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为数字人增加最小可用的显式目标链系统。

**Architecture:** 扩展 `Goal` 模型与仓储，使目标持有 `chain_id / parent_goal_id / generation`。世界事件生成链头目标，已完成的链目标在自主循环中自动派生下一代目标，并切换为当前活跃目标。

**Tech Stack:** Python, FastAPI, pytest
