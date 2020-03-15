import torch
import os
from collections import OrderedDict
import numpy as np
import cv2
import torch


def bbox_overlaps(bboxes1, bboxes2, mode='iou', is_aligned=False):
    """Calculate overlap between two set of bboxes.

    If ``is_aligned`` is ``False``, then calculate the ious between each bbox
    of bboxes1 and bboxes2, otherwise the ious between each aligned pair of
    bboxes1 and bboxes2.

    Args:
        bboxes1 (Tensor): shape (m, 4) in <x1, y1, x2, y2> format.
        bboxes2 (Tensor): shape (n, 4) in <x1, y1, x2, y2> format.
            If is_aligned is ``True``, then m and n must be equal.
        mode (str): "iou" (intersection over union) or iof (intersection over
            foreground).

    Returns:
        ious(Tensor): shape (m, n) if is_aligned == False else shape (m, 1)

    Example:
        >>> bboxes1 = torch.FloatTensor([
        >>>     [0, 0, 10, 10],
        >>>     [10, 10, 20, 20],
        >>>     [32, 32, 38, 42],
        >>> ])
        >>> bboxes2 = torch.FloatTensor([
        >>>     [0, 0, 10, 20],
        >>>     [0, 10, 10, 19],
        >>>     [10, 10, 20, 20],
        >>> ])
        >>> bbox_overlaps(bboxes1, bboxes2)
        tensor([[0.5238, 0.0500, 0.0041],
                [0.0323, 0.0452, 1.0000],
                [0.0000, 0.0000, 0.0000]])

    Example:
        >>> empty = torch.FloatTensor([])
        >>> nonempty = torch.FloatTensor([
        >>>     [0, 0, 10, 9],
        >>> ])
        >>> assert tuple(bbox_overlaps(empty, nonempty).shape) == (0, 1)
        >>> assert tuple(bbox_overlaps(nonempty, empty).shape) == (1, 0)
        >>> assert tuple(bbox_overlaps(empty, empty).shape) == (0, 0)
    """

    assert mode in ['iou', 'iof']

    rows = bboxes1.size(0)
    cols = bboxes2.size(0)
    if is_aligned:
        assert rows == cols

    if rows * cols == 0:
        return bboxes1.new(rows, 1) if is_aligned else bboxes1.new(rows, cols)

    if is_aligned:
        lt = torch.max(bboxes1[:, :2], bboxes2[:, :2])  # [rows, 2]
        rb = torch.min(bboxes1[:, 2:], bboxes2[:, 2:])  # [rows, 2]

        wh = (rb - lt + 1).clamp(min=0)  # [rows, 2]
        overlap = wh[:, 0] * wh[:, 1]
        area1 = (bboxes1[:, 2] - bboxes1[:, 0] + 1) * (
            bboxes1[:, 3] - bboxes1[:, 1] + 1)

        if mode == 'iou':
            area2 = (bboxes2[:, 2] - bboxes2[:, 0] + 1) * (
                bboxes2[:, 3] - bboxes2[:, 1] + 1)
            ious = overlap / (area1 + area2 - overlap)
        else:
            ious = overlap / area1
    else:
        lt = torch.max(bboxes1[:, None, :2], bboxes2[:, :2])  # [rows, cols, 2]
        rb = torch.min(bboxes1[:, None, 2:], bboxes2[:, 2:])  # [rows, cols, 2]

        wh = (rb - lt + 1).clamp(min=0)  # [rows, cols, 2]
        overlap = wh[:, :, 0] * wh[:, :, 1]
        area1 = (bboxes1[:, 2] - bboxes1[:, 0] + 1) * (
            bboxes1[:, 3] - bboxes1[:, 1] + 1)

        if mode == 'iou':
            area2 = (bboxes2[:, 2] - bboxes2[:, 0] + 1) * (
                bboxes2[:, 3] - bboxes2[:, 1] + 1)
            ious = overlap / (area1[:, None] + area2 - overlap)
        else:
            ious = overlap / (area1[:, None])

    return ious

def ensure_dir(path):
  if not os.path.isdir(path):
    os.makedirs(path)


def module2weight(moduledict):
  newdict = OrderedDict()
  for k, v in moduledict.items():
    newdict.update({k.replace('module.', ''): v})
  return newdict

class AverageMeter(object):
  """Computes and stores the average and current value"""

  def __init__(self):
    self.reset()

  def reset(self):
    # self.val = 0
    self.avg = 0
    self.sum = 0
    self.count = 1

  def update(self, temp_sum, n=1):
    # self.val = val
    self.sum += temp_sum
    self.count += n
    # self.avg = float(self.sum)/ float(self.count)

  def get_avg(self):
    return float(self.sum) / float(self.count)

def img_preprocess2(image, bboxes, target_shape, correct_box=True, keepratio=True):
  """
  RGB转换 -> resize(resize不改变原图的高宽比) -> normalize
  并可以选择是否校正bbox
  :param image_org: 要处理的图像
  :param target_shape: 对图像处理后，期望得到的图像shape，存储格式为(h, w)
  :return: 处理之后的图像，shape为target_shape
  """
  h_target, w_target = target_shape
  h_org, w_org, _ = image.shape

  image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB).astype(np.float32)
  if not keepratio:
    ratio_w = w_target / w_org
    ratio_h = h_target / h_org
    image = cv2.resize(image, target_shape, interpolation=cv2.INTER_LINEAR) / 255.0
    if correct_box:
      bboxes[:, [0, 2]] = bboxes[:, [0, 2]] * ratio_w
      bboxes[:, [1, 3]] = bboxes[:, [1, 3]] * ratio_h
      return image, bboxes
    return image
  resize_ratio = min(1.0 * w_target / w_org, 1.0 * h_target / h_org)
  resize_w = int(resize_ratio * w_org)
  resize_h = int(resize_ratio * h_org)
  image_resized = cv2.resize(image, (resize_w, resize_h))
  image_paded = np.full((h_target, w_target, 3), 128.0)
  dw = int((w_target - resize_w) / 2)
  dh = int((h_target - resize_h) / 2)
  image_paded[dh:resize_h + dh, dw:resize_w + dw, :] = image_resized
  image = image_paded / 255.0

  if correct_box:
    bboxes[:, [0, 2]] = bboxes[:, [0, 2]] * resize_ratio + dw
    bboxes[:, [1, 3]] = bboxes[:, [1, 3]] * resize_ratio + dh
    return image, bboxes
  return image


import socket


def get_host_ip():
    """
    get host ip address
    获取本机IP地址

    :return:
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    finally:
        s.close()

    return ip


def is_port_used(ip, port):
    """
    check whether the port is used by other program
    检测端口是否被占用

    :param ip:
    :param port:
    :return:
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, port))
        return True
    except OSError:
        return False
    finally:
        s.close()
def pick_avail_port():
    for port in range(23450,23460):
        if not is_port_used('127.0.0.1',port):
            return port

# 测试
if __name__ == '__main__':
    host_ip = get_host_ip()
    print(host_ip)
    print(is_port_used(host_ip, 23457))