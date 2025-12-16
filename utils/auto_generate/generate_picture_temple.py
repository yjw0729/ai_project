import os
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime


def generate_accurate_id_card_template(output_path=None, file_name=None):
    """
    根据用户描述的准确样式生成身份证模板
    """
    try:
        # 设置路径
        if output_path is None:
            output_path = os.getcwd()

        if file_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"accurate_id_card_{timestamp}.png"

        os.makedirs(output_path, exist_ok=True)
        full_path = os.path.join(output_path, file_name)

        # 身份证标准尺寸 (85.6mm × 54mm 按300dpi计算)
        width, height = 1011, 638  # 更准确的比例

        # 创建图片
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)

        # 主边框
        draw.rectangle([10, 10, width - 10, height - 10], outline='black', width=3)

        # 尝试加载字体
        try:
            title_font = ImageFont.truetype("simhei.ttf", 36)  # 标题字体稍大
            normal_font = ImageFont.truetype("simhei.ttf", 28)
            small_font = ImageFont.truetype("simhei.ttf", 24)
        except:
            # 如果字体不可用，使用默认字体
            title_font = ImageFont.load_default()
            normal_font = ImageFont.load_default()
            small_font = ImageFont.load_default()

        # 标题 - 顶部居中
        title = "居民身份证"
        title_bbox = draw.textbbox((0, 0), title, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width - title_width) // 2
        draw.text((title_x, 30), title, fill='black', font=title_font)

        # 左侧信息区域
        info_x = 50
        start_y = 100
        line_height = 45

        fields = [
            "姓名:",
            "性别:",
            "民族:",
            "出生:    年   月   日",
            "住址:",
            "公民身份号码:",
            "签发机关:",
            "有效期限:"
        ]

        # 绘制左侧信息字段
        for i, field in enumerate(fields):
            y_pos = start_y + i * line_height
            draw.text((info_x, y_pos), field, fill='black', font=normal_font)

            # 添加下划线（除了日期行）
            if "年   月   日" not in field:
                underline_y = y_pos + 35
                if field in ["住址:", "公民身份号码:"]:
                    # 长下划线
                    draw.line([(info_x + 150, underline_y), (width - 300, underline_y)],
                              fill='black', width=2)
                else:
                    # 短下划线
                    draw.line([(info_x + 150, underline_y), (info_x + 350, underline_y)],
                              fill='black', width=2)

        # 右侧区域 - 两个矩形框
        right_x = width - 250

        # 第一个矩形框（红色边框）- 国徽区域
        draw.rectangle([right_x, 100, right_x + 180, 250], outline='red', width=3)
        draw.text((right_x + 60, 160), "国徽", fill='red', font=small_font)

        # 第二个矩形框（蓝色边框）- 照片区域
        draw.rectangle([right_x, 280, right_x + 180, 430], outline='blue', width=3)
        draw.text((right_x + 60, 340), "照片", fill='blue', font=small_font)

        # 底部水印
        watermark = "仅用于测试目的"
        watermark_bbox = draw.textbbox((0, 0), watermark, font=small_font)
        watermark_width = watermark_bbox[2] - watermark_bbox[0]
        watermark_x = (width - watermark_width) // 2
        draw.text((watermark_x, height - 50), watermark, fill='gray', font=small_font)

        # 保存图片
        img.save(full_path, 'PNG', quality=95)
        print(f"准确的身份证模板已生成：{full_path}")
        return full_path

    except Exception as e:
        print(f"生成时出错：{str(e)}")
        return None


def generate_simple_fallback():
    """备用方案：如果上面复杂版本有问题，使用这个简化版"""
    try:
        from PIL import Image, ImageDraw

        img = Image.new('RGB', (800, 500), color='white')
        draw = ImageDraw.Draw(img)

        # 简单绘制主要元素
        draw.rectangle([10, 10, 790, 490], outline='black', width=2)
        draw.text((300, 30), "居民身份证", fill='black')

        # 左侧信息
        info = ["姓名:", "性别:", "民族:", "出生:年 月 日", "住址:", "公民身份号码:"]
        for i, text in enumerate(info):
            draw.text((50, 80 + i * 40), text, fill='black')

        # 右侧框
        draw.rectangle([550, 80, 750, 200], outline='red', width=2)  # 国徽
        draw.rectangle([550, 220, 750, 340], outline='blue', width=2)  # 照片

        img.save("simple_id_template.png")
        print("简化版模板已生成：simple_id_template.png")

    except Exception as e:
        print(f"连简化版也出错：{e}")


# 使用示例
if __name__ == "__main__":
    # 尝试生成准确版本
    result = generate_accurate_id_card_template("./templates")

    if not result:
        print("尝试生成简化版本...")
        generate_simple_fallback()