import numpy as np
import torch
import torch.nn.functional as F
import torchvision.transforms as TF
import torchvision.datasets as datasets
import kornia
# `utils` is RL-ViGen's own module and is only needed to resolve the Places365 path through
# cfgs/aug_config.cfg. Imported lazily inside _load_places so that importing this module does
# not require RL-ViGen on sys.path -- RAD needs random_shift, not places365.
import os


places_dataloader = None
places_iter = None


def _load_places(batch_size=256, image_size=84, num_workers=16, use_val=False):
	global places_dataloader, places_iter
	partition = 'val' if use_val else 'train'
	print(f'Loading {partition} partition of places365_standard...')
	# Resolve RL-ViGen's dataset list. Prefer its own `utils.load_config`; fall back to reading
	# cfgs/aug_config.cfg directly, so this works whether or not RL-ViGen is on sys.path.
	try:
		import utils            # noqa: E402
		_data_dirs = utils.load_config('datasets')
	except Exception:
		import json as _json, os as _os
		_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
		_cfg = _os.path.join(_root, 'RL-ViGen-upstream', 'cfgs', 'aug_config.cfg')
		_data_dirs = _json.load(open(_cfg))['datasets'] if _os.path.exists(_cfg) else []
	for data_dir in _data_dirs:
		if os.path.exists(data_dir):
			# PATCHED (many-gens-rl-vigen): pick a partition that EXISTS instead of falling
			# back to the parent directory. Upstream's fallback points ImageFolder at the whole
			# data root, which indexes every file under it as one class -- slow, and it silently
			# changes what the overlay distribution IS. We ship the val split (~2 GB) rather than
			# train (~24 GB); see setup/fetch_overlay_dataset.sh. The partition actually used is
			# printed, because it is a protocol-relevant choice.
			fp = None
			for _part in (partition, 'val', 'train'):
				_cand = os.path.join(data_dir, 'places365_standard', _part)
				if os.path.isdir(_cand):
					fp = _cand
					print(f'[overlay] places365_standard/{_part} from {data_dir}')
					break
			if fp is None:
				continue
			places_dataloader = torch.utils.data.DataLoader(
				datasets.ImageFolder(fp, TF.Compose([
					TF.RandomResizedCrop(image_size),
					TF.RandomHorizontalFlip(),
					TF.ToTensor()
				])),
				batch_size=batch_size, shuffle=True,
				num_workers=num_workers, pin_memory=True)
			places_iter = iter(places_dataloader)
			break
	if places_iter is None:
		raise FileNotFoundError('failed to find places365 data at any of the specified paths')
	print('Loaded dataset from', data_dir)


def _get_places_batch(batch_size):
	global places_iter
	try:
		imgs, _ = next(places_iter)
		if imgs.size(0) < batch_size:
			places_iter = iter(places_dataloader)
			imgs, _ = next(places_iter)
	except StopIteration:
		places_iter = iter(places_dataloader)
		imgs, _ = next(places_iter)
	return imgs


def random_overlay(x, dataset='places365_standard'):
	"""Randomly overlay an image from Places"""
	global places_iter
	alpha = 0.5

	if dataset == 'places365_standard':
		if places_dataloader is None:
			_load_places(batch_size=x.size(0), image_size=x.size(-1))
		# PATCHED (many-gens-rl-vigen): follow the observation's device.
		# This is the SAME defect as RL-ViGen's utils.py, which patch P4 fixes -- and it
		# survived here because this is a SEPARATE vendored copy of random_overlay that SODA
		# imports. Fixing the upstream instance and not this one is precisely the
		# fix-the-instance-not-the-class failure docs/RIGOR.md section 4 warns about; SVEA and
		# SGQN came back green while SODA still died on the real simulator.
		imgs = _get_places_batch(batch_size=x.size(0)).repeat(1, x.size(1)//3, 1, 1)
		imgs = imgs.to(x.device)
	else:
		raise NotImplementedError(f'overlay has not been implemented for dataset "{dataset}"')

	return ((1-alpha)*(x/255.) + (alpha)*imgs)*255.


def random_conv(x):
	"""Applies a random conv2d, deviates slightly from https://arxiv.org/abs/1910.05396"""
	n, c, h, w = x.shape
	for i in range(n):
		weights = torch.randn(3, 3, 3, 3).to(x.device)
		temp_x = x[i:i+1].reshape(-1, 3, h, w)/255.
		temp_x = F.pad(temp_x, pad=[1]*4, mode='replicate')
		out = torch.sigmoid(F.conv2d(temp_x, weights))*255.
		total_out = out if i == 0 else torch.cat([total_out, out], axis=0)
	return total_out.reshape(n, c, h, w)


def batch_from_obs(obs, batch_size=32):
	"""Copy a single observation along the batch dimension"""
	if isinstance(obs, torch.Tensor):
		if len(obs.shape)==3:
			obs = obs.unsqueeze(0)
		return obs.repeat(batch_size, 1, 1, 1)

	if len(obs.shape)==3:
		obs = np.expand_dims(obs, axis=0)
	return np.repeat(obs, repeats=batch_size, axis=0)


def prepare_pad_batch(obs, next_obs, action, batch_size=32):
	"""Prepare batch for self-supervised policy adaptation at test-time"""
	batch_obs = batch_from_obs(torch.from_numpy(obs).to('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'), batch_size)
	batch_next_obs = batch_from_obs(torch.from_numpy(next_obs).to('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu'), batch_size)
	batch_action = torch.from_numpy(action).to('cuda' if torch.cuda.is_available() else 'mps' if torch.backends.mps.is_available() else 'cpu').unsqueeze(0).repeat(batch_size, 1)

	return random_crop_cuda(batch_obs), random_crop_cuda(batch_next_obs), batch_action


def identity(x):
	return x


def random_shift(imgs, pad=4):
	"""Vectorized random shift, imgs: (B,C,H,W), pad: #pixels"""
	_,_,h,w = imgs.shape
	imgs = F.pad(imgs, (pad, pad, pad, pad), mode='replicate')
	return kornia.augmentation.RandomCrop((h, w))(imgs)


def random_crop(x, size=84, w1=None, h1=None, return_w1_h1=False):
	"""Vectorized CUDA implementation of random crop, imgs: (B,C,H,W), size: output size"""
	assert (w1 is None and h1 is None) or (w1 is not None and h1 is not None), \
		'must either specify both w1 and h1 or neither of them'
	assert isinstance(x, torch.Tensor) and x.is_cuda, \
		'input must be CUDA tensor'
	
	n = x.shape[0]
	img_size = x.shape[-1]
	crop_max = img_size - size

	if crop_max <= 0:
		if return_w1_h1:
			return x, None, None
		return x

	x = x.permute(0, 2, 3, 1)

	if w1 is None:
		w1 = torch.LongTensor(n).random_(0, crop_max)
		h1 = torch.LongTensor(n).random_(0, crop_max)

	windows = view_as_windows_cuda(x, (1, size, size, 1))[..., 0,:,:, 0]
	cropped = windows[torch.arange(n), w1, h1]

	if return_w1_h1:
		return cropped, w1, h1

	return cropped


def view_as_windows_cuda(x, window_shape):
	"""PyTorch CUDA-enabled implementation of view_as_windows"""
	assert isinstance(window_shape, tuple) and len(window_shape) == len(x.shape), \
		'window_shape must be a tuple with same number of dimensions as x'
	
	slices = tuple(slice(None, None, st) for st in torch.ones(4).long())
	win_indices_shape = [
		x.size(0),
		x.size(1)-int(window_shape[1]),
		x.size(2)-int(window_shape[2]),
		x.size(3)    
	]

	new_shape = tuple(list(win_indices_shape) + list(window_shape))
	strides = tuple(list(x[slices].stride()) + list(x.stride()))

	return x.as_strided(new_shape, strides)
