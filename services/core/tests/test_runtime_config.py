from app.runtime_ext.runtime_config import get_runtime_config


def test_runtime_config_self_heals_missing_folder_permissions_field():
    config = get_runtime_config()
    previous_permissions = config.list_folder_permissions()

    try:
        config.clear_folder_permissions()
        if hasattr(config, "_folder_permissions"):
            delattr(config, "_folder_permissions")

        healed = get_runtime_config()
        assert healed.list_folder_permissions() == []

        healed.set_folder_permission("/tmp/runtime-config-heal", "read_only")
        assert healed.list_folder_permissions() == [("/tmp/runtime-config-heal", "read_only")]
    finally:
        restored = get_runtime_config()
        restored.clear_folder_permissions()
        for path, access_level in previous_permissions:
            restored.set_folder_permission(path, access_level)
