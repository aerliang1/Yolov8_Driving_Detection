// 公共检测逻辑（摄像头检测、重置数据、检测统计等）

// 启动后端摄像头检测流
function startBackendCameraStream() {
  console.log('=== 启动后端摄像头检测流 ===');
  const model = $('#model-select').val();
  const username = window.currentUsername || 'monitor_user';
  if (!model) {
    console.error('未选择模型');
    return;
  }
  const hiddenImg = document.createElement('img');
  hiddenImg.style.display = 'none';
  hiddenImg.id = 'backend-camera-stream';
  const streamUrl = `${API_BASE_URL}/api/stream/camera?index=0&model=${encodeURIComponent(model)}&username=${encodeURIComponent(username)}`;
  hiddenImg.src = streamUrl;
  document.body.appendChild(hiddenImg);
  console.log('后端摄像头检测流已启动:', streamUrl);
  addLog('后端检测流已启动', 'success');
}

// 停止后端摄像头检测流
function stopBackendCameraStream() {
  const hiddenImg = document.getElementById('backend-camera-stream');
  if (hiddenImg) {
    hiddenImg.src = '';
    hiddenImg.remove();
    console.log('后端摄像头检测流已停止');
  }
}

// 启动定时检测统计
function startPeriodicDetection() {
  console.log('=== 启动定时检测统计 ===');
  if (window.detectionInterval) {
    clearInterval(window.detectionInterval);
  }
  const username = window.currentUsername || 'monitor_user';
  window.detectionInterval = setInterval(function() {
    $.ajax({
      url: API_BASE_URL + '/api/get_detected_objects',
      type: 'GET',
      data: { username: username },
      timeout: 5000,
      success: function(response) {
        if (response.success) {
          updateDetectionStats(response);
        }
      }
    });
  }, 1000);
  addLog('定时检测统计已启动', 'success');
}

// 更新检测统计信息
function updateDetectionStats(result) {
  var detectionInfo = result.detection_info || {};
  $('#closed-eyes-count').text(detectionInfo.closed_eyes_count || 0);
  $('#open-mouth-count').text(detectionInfo.open_mouth_count || 0);
  $('#open-eyes-count').text(detectionInfo.open_eyes_count || 0);
  $('#closed-mouth-count').text(detectionInfo.closed_mouth_count || 0);
  $('#total-detections').text(detectionInfo.total_detections || 0);
  $('#fatigue-indicators').text(result.fatigue_level || '无');
  $('#detection-time').text((detectionInfo.total_frames ? (detectionInfo.total_frames / 25.0).toFixed(1) : '0') + '秒');
  // 设置颜色
  const fatigueColors = {
    'none': '#00FF00',
    'mild': '#FFD700',
    'moderate': '#FF8C00',
    'severe': '#FF0000'
  };
  const color = fatigueColors[result.fatigue_level] || '#333';
  $('#closed-eyes-count, #open-mouth-count, #fatigue-indicators').css('color', color);
  $('#open-eyes-count, #closed-mouth-count, #total-detections').css('color', '#333');
}

// 重置数据
function resetDetection() {
  console.log('=== 重置数据被调用 ===');
  console.log('重置数据时 currentDetectionType:', window.currentDetectionType);

  const username = window.currentUsername || 'monitor_user';

  layer.confirm('确定要重置当前的检测数据吗？这将清除所有累计的统计信息。', {
    btn: ['确定', '取消'],
    icon: 3,
    title: '重置数据确认'
  }, function(index) {
    // 确定重置
    layer.close(index);

    // 显示重置中状态
    layer.msg('正在重置数据...', {icon: 16, time: 1000});

    // 调用后端重置API
    $.ajax({
      url: API_BASE_URL + '/api/camera/reset',
      type: 'POST',
      contentType: 'application/json',
      data: JSON.stringify({ username: username }),
      success: function(response) {
        console.log('重置响应:', response);
        if (response.success) {
          // 清零右侧统计数据
          $('#closed-eyes-count').text('0');
          $('#open-mouth-count').text('0');
          $('#open-eyes-count').text('0');
          $('#closed-mouth-count').text('0');
          $('#total-detections').text('0');
          $('#fatigue-indicators').text('无');
          $('#detection-time').text('0秒');

          // 重置颜色为绿色（不疲劳）
          $('#closed-eyes-count, #open-mouth-count, #fatigue-indicators').css('color', '#00FF00');
          $('#open-eyes-count, #closed-mouth-count, #total-detections').css('color', '#333');

          // 更新疲劳等级显示
          if (window.currentDetectionType) {
            updateDetectionStatus(window.currentDetectionType + '检测', '检测中...', '不疲劳');
          }

          // 如果后端建议重新启动检测流，则重新启动
          if (response.restart_detection && window.currentDetectionType === 'camera') {
            console.log('=== 重新启动摄像头检测流 ===');
            addLog('重新启动检测流...', 'info');

            // 1. 先真正停止后端检测流
            $.ajax({
              url: API_BASE_URL + '/api/detect/camera/stop',
              type: 'POST',
              contentType: 'application/json',
              data: JSON.stringify({ username: username }),
              success: function(stopResponse) {
                console.log('后端检测流停止成功:', stopResponse);
              },
              error: function(xhr, status, error) {
                console.error('停止后端检测流失败:', error);
              }
            });

            // 2. 停止前端的隐藏检测流
            stopBackendCameraStream();

            // 3. 停止定时检测
            if (window.detectionInterval) {
              clearInterval(window.detectionInterval);
              window.detectionInterval = null;
            }

            // 4. 延迟2秒后重新启动，确保后端完全停止和重置
            setTimeout(function() {
              console.log('开始重新启动检测流...');

              // 重新启动后端摄像头检测流
              startBackendCameraStream();

              // 重新启动定时检测统计
              startPeriodicDetection();

              addLog('检测流重新启动完成', 'success');
            }, 2000);
          }

          layer.msg('数据重置成功，检测流已重新启动', {icon: 1});
          addLog('检测数据已重置，检测流重新启动', 'success');

        } else {
          layer.msg('重置数据失败: ' + response.message, {icon: 2});
          addLog('重置数据失败: ' + response.message, 'error');
        }
      },
      error: function(xhr, status, error) {
        console.error('重置请求失败:', xhr, status, error);
        layer.msg('重置数据请求失败: ' + error, {icon: 2});
        addLog('重置数据请求失败: ' + error, 'error');
      }
    });
  });
}