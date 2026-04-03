# 世界事件进入 GPT 上下文 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把最近相关的世界事件接入 `/chat` 的模型上下文。

**Architecture:** 扩展 `build_chat_messages`，从记忆仓储中抽取相关的 `world` 事件，并以 `system` 消息形式插入到真实聊天消息之前。保持已有聊天记忆检索逻辑不变。

**Tech Stack:** Python, FastAPI, pytest
