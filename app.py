# video_merger/app.py
from flask import Flask, render_template, request
from datetime import datetime
import random
import os
import hashlib
import mysql.connector
from moviepy.editor import (
    VideoFileClip, 
    AudioFileClip, 
    concatenate_videoclips,
    concatenate_audioclips
)
from itertools import permutations

app = Flask(__name__)

# MySQL数据库连接配置
from dotenv import load_dotenv
load_dotenv()

db_config = {
    'user': os.getenv('DB_USER'),      # 在.env文件中设置: DB_USER=你的数据库用户名
    'password': os.getenv('DB_PASSWORD'), # 在.env文件中设置: DB_PASSWORD=你的数据库密码
    'host': os.getenv('DB_HOST'),      # 在.env文件中设置: DB_HOST=数据库主机地址(如localhost)
    'database': os.getenv('DB_NAME'),  # 在.env文件中设置: DB_NAME=数据库名称
    'port': int(os.getenv('DB_PORT'))  # 在.env文件中设置: DB_PORT=数据库端口(如3306)
}

def calculate_md5(file_path):
    """计算文件的MD5值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge_videos():
    # 获取用户上传的文件
    uploaded_videos = request.files.getlist('video_files[]')
    uploaded_bgms = request.files.getlist('bgm[]')
    # bgm生效位置，默认第一个视频
    audio_start_video = int(request.form.get('audio_start_video', 1))
    merge_name = request.form.get('merged_name', '')
    
    
    # 检查合并名称是否为空
    if not merge_name:
        return "请输入合并后的视频名称"


    video_clips = []

    # 保存上传的视频文件
    # 确保目录存在
    upload_dir = os.path.join('uploads', merge_name)
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
        
    for video in uploaded_videos:
        video_path = os.path.join(upload_dir, video.filename)
        # 检查文件是否已存在
        if not os.path.exists(video_path):
            video.save(video_path)
        video_clips.append(video_path)
    # 检查下标的有效性
    fixed_videos = {}
    random_videos = []
    for i in range(len(uploaded_videos)):
        index = request.form.get('video_index_' + str(i))
        if index:  # 如果下标不为空
            index = int(index) - 1  # 转换为0索引
            if index < 0 or index >= len(video_clips):
                return "下标超出范围！"
            if index in fixed_videos:
                return "下标重复！"
            fixed_videos[index] = video_clips[i]  # 固定视频
        else:
            random_videos.append(video_clips[i])  # 随机视频
    # 生成合并效果
    merged_videos = []

    # 保存上传的背景音乐
    # 确保bgms目录存在
    bgm_dir = 'bgms'
    if not os.path.exists(bgm_dir):
        os.makedirs(bgm_dir)
        
    # 保存背景音乐文件
    for bgm in uploaded_bgms:
        bgm_path = os.path.join(bgm_dir, bgm.filename)
        # 检查文件是否已存在
        if not os.path.exists(bgm_path):
            bgm.save(bgm_path)

    # 生成固定视频的合并列表
    # 创建一个列表,用于存储所有需要随机排列的位置
    random_positions = []
    for i in range(len(video_clips)):
        if i not in fixed_videos:
            random_positions.append(i)
            
    # 对随机视频进行全排列
    for perm in permutations(random_videos):
        # 创建一个合并列表,初始化为None
        merged_list = [None] * len(video_clips)
        
        # 先把固定位置的视频放进去
        for pos, video in fixed_videos.items():
            merged_list[pos] = video
            
        # 再把随机视频按照排列填充到剩余位置
        for pos, video in zip(random_positions, perm):
            merged_list[pos] = video
            
        merged_videos.append(merged_list)

    print(merged_videos)
    

    for final_video in merged_videos:
        # 合并视频
        video_clips_to_merge = [VideoFileClip(v) for v in final_video]
        final_video_clip = concatenate_videoclips(video_clips_to_merge)

        # 处理背景音乐
        if uploaded_bgms:
            # 随机选择一个背景音乐
            random_bgm = random.choice(uploaded_bgms)
            audio_path = os.path.join(bgm_dir, random_bgm.filename)
            audio_clip = AudioFileClip(audio_path)
            
            # 计算音频开始时间
            audio_start_time = 0
            if audio_start_video > 1:
                # 计算前面视频的总时长作为音频开始时间
                for i in range(audio_start_video - 1):
                    audio_start_time += video_clips_to_merge[i].duration
            
            # 裁剪音频
            remaining_duration = final_video_clip.duration - audio_start_time
            if audio_clip.duration > remaining_duration:
                audio_clip = audio_clip.subclip(0, remaining_duration)
            else:
                # 如果背景音乐长度不够,保留视频原声
                remaining_video_duration = final_video_clip.duration - (audio_start_time + audio_clip.duration)
                if remaining_video_duration > 0:
                    original_audio = final_video_clip.audio.subclip(audio_start_time + audio_clip.duration)
                    audio_clip = concatenate_audioclips([audio_clip, original_audio])
            
            # 创建前面视频的原声音频片段
            # 从原始视频中提取前面部分的音频
            original_audio_start = final_video_clip.audio.subclip(0, audio_start_time)
            
            # 合并静音和背景音乐
            final_audio = concatenate_audioclips([original_audio_start, audio_clip])
            
            # 插入音频
            final_video_clip = final_video_clip.set_audio(final_audio)
        # 创建merge目录(如果不存在)
        merge_dir = os.path.join("merge", merge_name)
        if not os.path.exists(merge_dir):
            os.makedirs(merge_dir)
            
        # 获取merge目录下已有的文件数量
        existing_files = len([f for f in os.listdir(merge_dir) if os.path.isfile(os.path.join(merge_dir, f))])
        
        # 生成新的文件名
        current_date = datetime.now().strftime('%m.%d')
        merged_video_file = os.path.join(merge_dir, f"{current_date} {merge_name}_{existing_files}.mp4")
        final_video_clip.write_videofile(merged_video_file)

        # 计算合并后视频的MD5值
        md5_hash = calculate_md5(merged_video_file)

        # 将结果插入到MySQL数据库
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        insert_query = "INSERT INTO video_records (video_name, md5_hash) VALUES (%s, %s)"
        cursor.execute(insert_query, (merged_video_file, md5_hash))
        conn.commit()
        cursor.close()
        conn.close()
    return "合并完成，生成了多个视频文件！"

if __name__ == '__main__':
    app.run(debug=True)