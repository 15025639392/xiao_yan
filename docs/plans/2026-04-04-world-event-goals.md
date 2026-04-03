# 世界事件驱动目标 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让最近世界事件能够在无活跃目标时驱动新的目标生成。

**Architecture:** 在 `AutonomyLoop` 的无活跃目标分支中增加世界事件回退路径。优先使用最新用户消息，找不到新的用户消息时改用最近世界事件，生成对应 goal 与 thought。

**Tech Stack:** Python, pytest
