"""调用 Tripo API 将图片转为 3D 模型"""
import asyncio, os, sys
from pathlib import Path
from tripo3d import TripoClient, TaskStatus

API_KEY = "tsk_VcTb_bY2f04u4iiql0vH579NcK4m8Oj_OzfxJIQ8wQO"
IMAGE_PATH = "/Users/ldy/Desktop/work/xiao_yan/ig_05316235a269e22c0169eb9e02201081919efd020e360c3b6c.png"
OUTPUT_DIR = "/Users/ldy/Desktop/work/xiao_yan/services/core/.data/tripo_output"


async def main():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    async with TripoClient(api_key=API_KEY) as client:
        # 查看余额
        balance = await client.get_balance()
        print(f"💰 账户余额: {balance}")

        # 创建图片转3D任务
        print(f"\n📤 上传图片: {IMAGE_PATH}")
        task_id = await client.image_to_model(
            image=IMAGE_PATH,
            model_version="v3.1-20260211",
            texture_quality="detailed",
            geometry_quality="detailed",
            pbr=True,
            texture=True,
            texture_alignment="original_image",
        )
        print(f"✅ 任务已创建: {task_id}")

        # 等待完成
        print("\n⏳ 等待生成...")
        task = await client.wait_for_task(task_id, verbose=True)

        if task.status == TaskStatus.SUCCESS:
            print(f"\n🎉 生成成功！")
            print(f"   模型: {task.output}")

            # 下载模型文件
            print(f"\n📥 下载模型到: {OUTPUT_DIR}")
            files = await client.download_task_models(task, OUTPUT_DIR)
            for model_type, file_path in files.items():
                if file_path:
                    size_kb = Path(file_path).stat().st_size / 1024
                    print(f"   {model_type}: {file_path} ({size_kb:.1f} KB)")
        else:
            print(f"\n❌ 任务失败: status={task.status}")
            if hasattr(task, 'error'):
                print(f"   错误: {task.error}")


if __name__ == "__main__":
    asyncio.run(main())
