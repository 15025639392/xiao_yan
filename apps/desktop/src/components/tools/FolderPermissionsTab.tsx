import { useEffect, useState } from "react";
import type { ChatFolderPermission } from "../../lib/api";
import {
  fetchChatFolderPermissions,
  removeChatFolderPermission,
  upsertChatFolderPermission,
} from "../../lib/api";
import { pickDirectory } from "../../lib/tauri/dialog";
import {
  FolderOpen,
  FolderX,
  Loader2,
  Plus,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { InlineAlert } from "../ui/InlineAlert";
import { StatusBadge } from "../ui/StatusBadge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";

export function FolderPermissionsTab() {
  const [permissions, setPermissions] = useState<ChatFolderPermission[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [pathDraft, setPathDraft] = useState("");
  const [accessLevelDraft, setAccessLevelDraft] = useState<"read_only" | "full_access">("read_only");
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);

  useEffect(() => {
    loadPermissions();
  }, []);

  async function loadPermissions() {
    setIsLoading(true);
    setError("");
    try {
      const result = await fetchChatFolderPermissions();
      setPermissions(result.permissions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载目录权限失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function handlePickDirectory() {
    setError("");
    const selected = await pickDirectory();
    if (selected) {
      setPathDraft(selected);
    }
  }

  async function handleAdd() {
    const trimmed = pathDraft.trim();
    if (!trimmed) {
      setError("请先选择文件夹");
      return;
    }
    setIsSaving(true);
    setError("");
    try {
      const result = await upsertChatFolderPermission(trimmed, accessLevelDraft);
      setPermissions(result.permissions);
      setPathDraft("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加目录权限失败");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleRemove() {
    if (!removeTarget) return;
    setIsSaving(true);
    setError("");
    try {
      const result = await removeChatFolderPermission(removeTarget);
      setPermissions(result.permissions);
      setRemoveTarget(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除目录权限失败");
    } finally {
      setIsSaving(false);
    }
  }

  const isRemoveDialogOpen = removeTarget !== null;

  return (
    <div className="flex flex-col gap-5">
      {/* Header Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-[var(--radius-md)] bg-[var(--primary-muted)] text-[var(--primary)]">
              <Shield className="h-[1.125rem] w-[1.125rem]" />
            </div>
            <div>
              <CardTitle>目录权限</CardTitle>
              <CardDescription>管理小晏可访问的额外目录及其权限级别</CardDescription>
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {/* Directory Picker */}
          <div className="flex flex-col gap-3 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--bg-canvas)] p-3">
            <div className="flex items-center gap-3">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={isSaving}
                onClick={() => void handlePickDirectory()}
                className="shrink-0"
              >
                <FolderOpen className="h-4 w-4" />
                选择文件夹
              </Button>
              {pathDraft ? (
                <code
                  className="min-w-0 truncate rounded-[var(--radius-sm)] bg-[var(--bg-surface)] px-2 py-1 text-[0.8125rem] text-[var(--info)]"
                  title={pathDraft}
                >
                  {pathDraft}
                </code>
              ) : (
                <span className="text-[0.8125rem] text-[var(--text-tertiary)]">未选择</span>
              )}
            </div>

            <label className="inline-flex items-center gap-2 text-[0.8125rem] text-[var(--text-secondary)]">
              <Checkbox
                checked={accessLevelDraft === "full_access"}
                disabled={isSaving}
                onChange={(event) => {
                  setAccessLevelDraft(event.target.checked ? "full_access" : "read_only");
                }}
              />
              <span>完全访问（允许读写）</span>
            </label>

            <Button
              type="button"
              variant="default"
              size="sm"
              disabled={isSaving || !pathDraft.trim()}
              onClick={() => void handleAdd()}
              className="self-start"
            >
              {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              添加
            </Button>
          </div>

          {/* Error / Loading */}
          {error ? (
            <InlineAlert tone="danger">{error}</InlineAlert>
          ) : null}
          {isLoading ? (
            <div className="flex items-center gap-2 text-[0.8125rem] text-[var(--text-tertiary)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载中…
            </div>
          ) : null}
        </CardContent>
      </Card>

      {/* Permissions List */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>已授权目录</CardTitle>
            <span className="rounded-full bg-[var(--bg-surface-elevated)] px-2 py-0.5 text-[0.6875rem] font-semibold text-[var(--text-tertiary)]">
              {permissions.length}
            </span>
          </div>
          <CardDescription>
            小晏可以在这些目录中执行文件操作，受限于各自的权限级别
          </CardDescription>
        </CardHeader>
        <CardContent>
          {permissions.length === 0 && !isLoading ? (
            <div className="flex flex-col items-center gap-3 py-10 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-[var(--bg-surface-elevated)] text-[var(--text-muted)]">
                <FolderX className="h-6 w-6" />
              </div>
              <div>
                <p className="text-[0.875rem] font-medium text-[var(--text-secondary)]">
                  当前没有配置额外目录权限
                </p>
                <p className="mt-1 text-[0.75rem] text-[var(--text-tertiary)]">
                  点击上方"选择文件夹"添加需要授权的目录
                </p>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {permissions.map((perm) => (
                <div
                  key={perm.path}
                  className="group flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--bg-canvas)] px-3 py-2.5 transition-all duration-150 hover:border-[var(--border-strong)] hover:bg-[var(--bg-surface-elevated)]"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--bg-surface)] text-[var(--text-tertiary)] group-hover:text-[var(--primary)] transition-colors duration-150">
                      {perm.access_level === "full_access" ? (
                        <ShieldCheck className="h-4 w-4" />
                      ) : (
                        <ShieldAlert className="h-4 w-4" />
                      )}
                    </div>
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <code
                        className="truncate text-[0.8125rem] text-[var(--text-primary)]"
                        title={perm.path}
                      >
                        {perm.path}
                      </code>
                      <StatusBadge
                        tone={perm.access_level === "full_access" ? "danger" : "info"}
                        className={perm.access_level === "full_access" ? "status-badge--abandoned" : "status-badge--active"}
                      >
                        {perm.access_level === "full_access" ? "完全访问" : "只读"}
                      </StatusBadge>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="destructive"
                    size="icon"
                    disabled={isSaving}
                    onClick={() => setRemoveTarget(perm.path)}
                    aria-label={`删除 ${perm.path} 的权限`}
                    className="shrink-0 opacity-60 transition-opacity duration-150 group-hover:opacity-100"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Remove Confirm Dialog */}
      <Dialog open={isRemoveDialogOpen} onOpenChange={(open) => !open && setRemoveTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>确认删除权限</DialogTitle>
            <DialogDescription>
              确定要删除以下目录的访问权限吗？此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <div className="px-5">
            <code
              className="block truncate rounded-[var(--radius-sm)] bg-[var(--bg-canvas)] px-3 py-2 text-[0.8125rem] text-[var(--info)]"
              title={removeTarget ?? ""}
            >
              {removeTarget}
            </code>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setRemoveTarget(null)}
              disabled={isSaving}
            >
              取消
            </Button>
            <Button
              type="button"
              variant="destructive"
              size="sm"
              disabled={isSaving}
              onClick={() => void handleRemove()}
            >
              {isSaving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
