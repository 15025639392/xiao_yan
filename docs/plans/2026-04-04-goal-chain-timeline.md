# 目标链时间线视图 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在前端把目标链展示成可读的时间线。

**Architecture:** `GoalsPanel` 内部按 `chain_id` 分组目标，并在链组中按 `generation` 排序。现有目标状态按钮保留在每个时间线节点上。

**Tech Stack:** React, TypeScript, vitest
