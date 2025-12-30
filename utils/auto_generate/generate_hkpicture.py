from PIL import Image, ImageDraw, ImageFont
import os
import re
import io
import sys


def get_project_root():
    """
    获取项目根目录路径

    返回:
        str: 项目根目录的绝对路径
    """
    # 方法1: 尝试获取当前脚本所在目录，然后回溯到pytest_sxp根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 从当前脚本目录向上查找pytest_sxp目录
    current_dir = script_dir
    while current_dir and os.path.basename(current_dir) != 'pytest_sxp':
        parent = os.path.dirname(current_dir)
        if parent == current_dir:  # 到达根目录
            break
        current_dir = parent

    # 如果找到了pytest_sxp目录
    if os.path.basename(current_dir) == 'pytest_sxp':
        return current_dir

    # 方法2: 使用当前工作目录
    cwd = os.getcwd()
    if 'pytest_sxp' in cwd:
        # 从当前工作目录中查找pytest_sxp
        parts = cwd.split(os.sep)
        try:
            pytest_sxp_index = parts.index('pytest_sxp')
            project_root = os.sep.join(parts[:pytest_sxp_index + 1])
            return project_root
        except ValueError:
            pass

    # 方法3: 检查常见项目结构
    possible_paths = [
        r"D:\pythonProject\pytest_sxp",
        os.path.join(os.path.expanduser("~"), "pythonProject", "pytest_sxp"),
        os.path.join(os.getcwd(), "pytest_sxp"),
        "pytest_sxp"
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return os.path.abspath(path)

    # 如果都没找到，返回None，让用户选择
    return None


def find_template_image():
    """
    查找模板图片文件

    返回:
        str: 找到的模板图片路径，如果没找到则返回None
    """
    # 可能的图片文件名
    possible_filenames = [
        "business_registration.png",
        "business_registration.jpg",
    ]

    # 可能的子目录
    possible_subdirs = [
        "docs/picture",
        "docs/pictures",
        "docs/images",
        "picture",
        "pictures",
        "images",
        "doc/picture",
        "template/picture"
    ]

    # 1. 首先尝试获取项目根目录
    project_root = get_project_root()

    if project_root:
        print(f"项目根目录: {project_root}")

        # 在项目根目录下搜索
        for subdir in possible_subdirs:
            for filename in possible_filenames:
                full_path = os.path.join(project_root, subdir, filename)
                if os.path.exists(full_path):
                    print(f"找到模板图片: {full_path}")
                    return full_path

        # 如果没找到，在项目根目录下递归搜索
        print("在项目根目录下递归搜索模板图片...")
        for root, dirs, files in os.walk(project_root):
            for filename in possible_filenames:
                if filename in files:
                    full_path = os.path.join(root, filename)
                    print(f"找到模板图片: {full_path}")
                    return full_path

    # 2. 在当前目录下搜索
    current_dir = os.getcwd()
    print(f"当前目录: {current_dir}")

    for subdir in possible_subdirs:
        for filename in possible_filenames:
            full_path = os.path.join(current_dir, subdir, filename)
            if os.path.exists(full_path):
                print(f"找到模板图片: {full_path}")
                return full_path

    # 3. 在当前脚本目录下搜索
    script_dir = os.path.dirname(os.path.abspath(__file__))
    for subdir in possible_subdirs:
        for filename in possible_filenames:
            full_path = os.path.join(script_dir, subdir, filename)
            if os.path.exists(full_path):
                print(f"找到模板图片: {full_path}")
                return full_path

    # 4. 在常见位置搜索
    common_locations = [
        r"D:\pythonProject\pytest_sxp\docs\picture\business_registration.png",
        r"D:\pythonProject\pytest_sxp\docs\picture\business_registration.jpg",
        r"D:\pythonProject\pytest_sxp\docs\picture\test_hk01.jpg",
        r"D:\pythonProject\pytest_sxp\docs\picture\test.png",
        os.path.join(os.getcwd(), "business_registration.png"),
        os.path.join(os.getcwd(), "template.png"),
        os.path.join(script_dir, "template.png")
    ]

    for path in common_locations:
        if os.path.exists(path):
            print(f"找到模板图片: {path}")
            return path

    return None


def get_image_path_from_user():
    """
    从用户输入获取图片路径
    """
    print("未找到模板图片，请选择:")
    print("1. 手动输入图片路径")
    print("2. 浏览选择图片")

    choice = input("请选择 (1/2): ").strip()

    if choice == "1":
        path = input("请输入图片路径: ").strip()
        if os.path.exists(path):
            return path
        else:
            print(f"路径不存在: {path}")
            return None
    elif choice == "2":
        # 尝试使用文件对话框
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()  # 隐藏主窗口

            file_path = filedialog.askopenfilename(
                title="选择模板图片",
                filetypes=[("图片文件", "*.png;*.jpg;*.jpeg;*.bmp;*.gif"), ("所有文件", "*.*")]
            )

            if file_path:
                return file_path
            else:
                print("未选择文件")
                return None
        except:
            print("无法打开文件对话框，请手动输入路径")
            path = input("请输入图片路径: ").strip()
            return path if os.path.exists(path) else None
    else:
        print("无效选择")
        return None


def safe_image_open(image_path):
    """
    安全地打开图片，避免Pillow版本兼容性问题
    """
    try:
        # 方法1：直接打开
        return Image.open(image_path)
    except Exception as e:
        print(f"直接打开失败，尝试方法2: {e}")
        try:
            # 方法2：使用二进制方式打开
            with open(image_path, 'rb') as f:
                img_data = f.read()
            return Image.open(io.BytesIO(img_data))
        except Exception as e2:
            print(f"二进制方式打开失败，尝试方法3: {e2}")
            # 方法3：尝试以不同模式打开
            try:
                from PIL import ImageFile
                parser = ImageFile.Parser()
                with open(image_path, 'rb') as f:
                    chunk = f.read()
                    parser.feed(chunk)
                    while chunk:
                        chunk = f.read(1024)
                        parser.feed(chunk)
                return parser.close()
            except Exception as e3:
                raise ValueError(f"无法打开图片，请检查文件格式和路径: {e3}")


def modify_business_registration_number(image_path, new_number, output_path=None):
    """
    修改商业登记证图片中的登记证号码前8位

    参数：
    image_path: 原始图片路径
    new_number: 新的8位登记证号码（字符串，必须是8位数字）
    output_path: 输出图片路径（可选，默认在原文件名后添加_modified）
    """

    # 验证新号码格式
    if not re.match(r'^\d{8}$', new_number):
        raise ValueError("新号码必须是8位数字")

    # 打开原始图片（使用安全方式）
    try:
        img = safe_image_open(image_path)
    except Exception as e:
        raise ValueError(f"无法打开图片: {e}")

    print(f"图片信息: {img.format}, {img.size}, {img.mode}")

    # 创建可编辑的图片副本
    img_edit = img.copy()
    draw = ImageDraw.Draw(img_edit)

    # 尝试加载中文字体
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",  # Windows 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
        "C:/Windows/Fonts/arial.ttf",  # Windows Arial
    ]

    font = None
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                # 根据图片大小调整字体大小
                img_width, img_height = img.size
                font_size = max(13, min(24, int(img_height * 0.02)))
                font = ImageFont.truetype(font_path, font_size)
                print(f"使用字体: {font_path}, 大小: {font_size}")
                break
            except:
                continue

    # 如果没有找到字体，使用默认字体
    if font is None:
        try:
            font = ImageFont.load_default()
            print("使用默认字体")
        except:
            # 创建简单的位图字体
            font = ImageFont.load_default()

    # 根据图片信息设置坐标
    # 根据您提供的图片信息：500×656像素，登记证号码位置在146×12像素附近
    img_width, img_height = img.size

    # 根据图片尺寸调整坐标
    x1, y1 = 410, 600  # 左上角
    x2, y2 = 630, 650  # 右下角

    print(f"使用坐标: 左上角({x1}, {y1}), 右下角({x2}, {y2})")

    # 检查坐标是否在图片范围内
    if x1 < 0 or y1 < 0 or x2 > img_width or y2 > img_height:
        print(f"警告: 坐标超出图片范围，已调整")
        x1 = max(0, min(x1, img_width - 1))
        y1 = max(0, min(y1, img_height - 1))
        x2 = max(0, min(x2, img_width - 1))
        y2 = max(0, min(y2, img_height - 1))

    # 获取背景颜色
    try:
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        center_x = max(0, min(center_x, img_width - 1))
        center_y = max(0, min(center_y, img_height - 1))

        bg_color = img.getpixel((center_x, center_y))
        if isinstance(bg_color, tuple) and len(bg_color) >= 3:
            bg_color = bg_color[:3]
        else:
            bg_color = (bg_color, bg_color, bg_color) if isinstance(bg_color, int) else (255, 255, 255)
        print(f"背景颜色: {bg_color}")
    except:
        bg_color = (255, 255, 255)  # 白色背景
        print(f"使用默认背景颜色: {bg_color}")

    # 用背景色矩形覆盖原文本区域
    draw.rectangle([x1 - 2, y1 - 2, x2 + 2, y2 + 2], fill=bg_color, outline=None)

    # 构建新的登记证号码（保持格式一致）
    new_full_number = f"{new_number}-000-11-02-2"

    # 计算文本位置（居中）
    try:
        text_bbox = draw.textbbox((x1, y1), new_full_number, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # 居中位置
        text_x = x1 + (x2 - x1 - text_width) / 2
        text_y = y1 + (y2 - y1 - text_height) / 2

        # 确保文本在图片范围内
        text_x = max(0, min(text_x, img_width - text_width))
        text_y = max(0, min(text_y, img_height - text_height))

        # 写入新号码
        draw.text((text_x, text_y), new_full_number, fill="black", font=font)
        print(f"已将登记证号码修改为: {new_full_number}")

    except Exception as e:
        print(f"计算文本位置失败: {e}")
        # 如果计算失败，使用简单的位置
        draw.text((x1, y1), new_full_number, fill="black", font=font)

    # 保存图片
    if output_path is None:
        base, ext = os.path.splitext(image_path)
        output_path = f"{base}_modified{ext}"

    try:
        # 确保图片是RGB模式
        if img_edit.mode != 'RGB':
            print(f"转换图片模式: {img_edit.mode} -> RGB")
            img_edit = img_edit.convert('RGB')

        # 保存图片
        img_edit.save(output_path)
        print(f"修改完成！新图片已保存到: {output_path}")

    except Exception as e:
        print(f"保存图片失败: {e}")
        # 尝试保存为PNG格式
        if not output_path.lower().endswith('.png'):
            output_path = output_path.rsplit('.', 1)[0] + '.png'
            img_edit.save(output_path)
            print(f"已保存为PNG格式: {output_path}")

    return output_path


def main():
    """主函数"""
    print("=" * 60)
    print("商业登记证号码修改工具")
    print("=" * 60)

    # 自动查找模板图片
    print("正在查找模板图片...")
    image_path = find_template_image()

    if not image_path:
        print("未找到模板图片，请手动指定")
        image_path = get_image_path_from_user()

        if not image_path:
            print("无法获取图片路径，程序退出")
            return

    print(f"使用模板图片: {image_path}")

    # 获取新号码
    while True:
        new_number = input("请输入新的8位登记证号码: ").strip()
        if re.match(r'^\d{8}$', new_number):
            break
        print("错误: 请输入8位数字")

    # 询问输出路径
    base, ext = os.path.splitext(image_path)
    default_output = f"{base}_modified_{new_number}{ext}"
    output_path = input(f"请输入输出路径（留空使用默认: {default_output}）: ").strip()
    if not output_path:
        output_path = default_output

    try:
        # 使用自动坐标修改
        result = modify_business_registration_number(
            image_path,
            new_number,
            output_path
        )

        print(f"\n操作完成！")
        print(f"原始图片: {image_path}")
        print(f"修改后图片: {result}")

        # 询问是否打开图片
        open_image = input("是否打开修改后的图片? (y/n): ").lower()
        if open_image == 'y':
            try:
                import subprocess
                subprocess.Popen(['start', result], shell=True)
            except:
                print(f"无法自动打开图片，请手动查看: {result}")

    except Exception as e:
        print(f"修改失败: {e}")

        # 提供可能的解决方案
        print("\n可能的解决方案:")
        print("1. 更新Pillow库: pip install --upgrade Pillow")
        print("2. 重新安装Pillow: pip uninstall Pillow && pip install Pillow")
        print("3. 检查图片格式是否支持")
        print("4. 尝试将图片转换为其他格式（如PNG）")


def quick_modify():
    """
    快速修改函数
    """
    print("快速修改模式")
    print("=" * 30)

    # 自动查找模板图片
    image_path = find_template_image()

    if not image_path:
        print("未找到模板图片，请手动指定")
        image_path = get_image_path_from_user()

        if not image_path:
            print("无法获取图片路径，程序退出")
            return

    # 新号码
    new_number = "87654321"  # 您可以修改这里
    output_path = "modified_certificate.jpg"

    try:
        result = modify_business_registration_number(
            image_path,
            new_number,
            output_path
        )
        print(f"快速修改完成！文件保存为: {result}")

        # 尝试打开图片
        try:
            import subprocess
            subprocess.Popen(['start', result], shell=True)
        except:
            print(f"请手动查看: {result}")

    except Exception as e:
        print(f"快速修改失败: {e}")


def batch_modify():
    """
    批量修改函数
    """
    print("批量修改模式")
    print("=" * 30)

    # 自动查找模板图片
    image_path = find_template_image()

    if not image_path:
        print("未找到模板图片，请手动指定")
        image_path = get_image_path_from_user()

        if not image_path:
            print("无法获取图片路径，程序退出")
            return

    # 获取批量号码
    numbers = []
    print("请输入多个8位登记证号码（输入'q'结束输入）:")

    while True:
        num = input(f"请输入第{len(numbers) + 1}个号码: ").strip()
        if num.lower() == 'q':
            break

        if re.match(r'^\d{8}$', num):
            numbers.append(num)
            print(f"已添加号码: {num}")
        else:
            print("错误: 请输入8位数字或输入'q'结束")

    if not numbers:
        print("未输入任何号码，程序退出")
        return

    # 批量修改
    for i, num in enumerate(numbers, 1):
        try:
            base, ext = os.path.splitext(image_path)
            output_path = f"{base}_modified_{num}{ext}"

            result = modify_business_registration_number(
                image_path,
                num,
                output_path
            )
            print(f"[{i}/{len(numbers)}] 完成: {num} -> {result}")
        except Exception as e:
            print(f"[{i}/{len(numbers)}] 失败: {num}, 错误: {e}")

    print(f"\n批量修改完成！共处理 {len(numbers)} 个号码")


if __name__ == "__main__":
    # 检查Pillow版本
    try:
        import PIL

        print(f"Pillow版本: {PIL.__version__}")
    except:
        print("Pillow库未安装，尝试安装...")
        try:
            import subprocess
            import sys

            subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
            print("Pillow安装成功，请重新运行程序")
            sys.exit(0)
        except:
            print("Pillow安装失败，请手动安装: pip install Pillow")

    # 显示菜单
    print("=" * 60)
    print("商业登记证号码修改工具")
    print("=" * 60)
    print("请选择模式:")
    print("1. 单次修改（交互式）")
    print("2. 快速修改（使用默认号码）")
    print("3. 批量修改（多个号码）")

    choice = input("请输入选择 (1/2/3): ").strip()

    if choice == "1":
        main()
    elif choice == "2":
        quick_modify()
    elif choice == "3":
        batch_modify()
    else:
        print("无效选择，使用默认模式")
        main()