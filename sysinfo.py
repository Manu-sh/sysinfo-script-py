from os import uname, uname_result
from typing import Pattern, Any, Callable, Final, TypedDict, Optional
from threading import Thread
from enum import Enum
import subprocess, json, re


def get_cpu() -> str|None:

	class CpuInfo(TypedDict):
		model:            str |None
		freq:             str |None
		core:             int |None
		threads_per_core: int |None
		threads:          int |None
    
	data: CpuInfo = { 'model': None, 'freq': None, 'core': None, 'threads_per_core': None }

	with subprocess.Popen(['lscpu', '-J'], stdout=subprocess.PIPE, text=True) as process:
		for d in json.load(process.stdout)['lscpu']:
			if 'field' not in d:
				continue

			key: Final[str] = d['field'].lower()

			if key.startswith('model name'):
				data['model'] = d['data']
			elif key.startswith('cpu max mhz'):
				data['freq'] = float(d['data'].replace(',', '.')) / 1000
				data['freq'] = f'{data["freq"]:4.2f}GHz'
			elif key.startswith('core(s) per socket'):
				data['core'] = int(d['data'])
			elif key.startswith('thread(s) per core:'):
				data['threads_per_core'] = int(d['data'])

			if all(v is not None for v in data.values()):
				return f'{data["model"]} @ {data["freq"]} {data["core"]} cores {data["core"] * data["threads_per_core"]} threads'

	return None


def get_gpu() -> str | None:
	pattern: Final[Pattern] = re.compile(r'Display|3D|VGA')

	with subprocess.Popen(['lspci', '-mm'], stdout=subprocess.PIPE, text=True) as process:
		while line := process.stdout.readline():
			if not pattern.search(line):
				continue

			brand, model = re.findall(r'".*?"', line)[1:3]
			brand: str = re.search(r'(NVIDIA|AMD)', brand,  re.IGNORECASE).group(1) # other brand aren't implemented yet
			model: str = re.search(r'\[(.*)?\]', model).group(1)	
			return f'{brand} {model}'
	return None


def to_iec(in_bytes: int, precision: int = 2) -> str:
	PEBIBYTE: Final[int] = 1125899906842624
	TEBIBYTE: Final[int] = 1099511627776
	GIBIBYTE: Final[int] = 1073741824
	MEBIBYTE: Final[int] = 1048576
	KIBIBYTE: Final[int] = 1024

	if in_bytes >= PEBIBYTE:
		raise Exception('Invalid size')
	elif in_bytes >= TEBIBYTE:
		return f'{in_bytes / float(TEBIBYTE):.{precision}f}TiB'
	elif in_bytes >= GIBIBYTE:
		return f'{in_bytes / float(GIBIBYTE):.{precision}f}GiB'
	elif in_bytes >= MEBIBYTE:
		return f'{in_bytes / float(MEBIBYTE):.{precision}f}MiB'
	elif in_bytes >= KIBIBYTE:
		return f'{in_bytes / float(KIBIBYTE):.{precision}f}KiB'

	return f'{in_bytes / float(KIBIBYTE):.{precision}f}B'


def get_mem() -> str | None:
	
	class Memory(Enum):
		TOTAL    : Final[Pattern] = re.compile(r'^memtotal\s*:\s*(\d*?)\s*kb',     re.IGNORECASE)
		FREE     : Final[Pattern] = re.compile(r'^memfree\s*:\s*(\d*?)\s*kb',      re.IGNORECASE)
		AVAILABLE: Final[Pattern] = re.compile(r'^memavailable\s*:\s*(\d*?)\s*kb', re.IGNORECASE)
		#def __str__(self) -> str: return self.name
		#print(str(Memory.TOTAL))

	mem: dict[str, Any] = { 
		Memory.TOTAL.name    : None, 
		Memory.FREE.name     : None, 
		Memory.AVAILABLE.name: None 
	}

	to_bytes: Callable[[int], int] = lambda v: v * 1000

	with open('/proc/meminfo', 'r') as f_meminfo:
		while line := f_meminfo.readline():
			for enum in Memory:
				if r_match := enum.value.search(line):
					mem[ enum.name ] = to_bytes(int(r_match.group(1)))

	for v in mem.values():
		if v is None: return None

	return f'{ to_iec(mem[Memory.TOTAL.name] - mem[Memory.AVAILABLE.name]) } / { to_iec(mem[Memory.TOTAL.name])}'


def get_uname() -> str:
    u_name: uname_result = uname()
    return f'{u_name.sysname} {u_name.release} {u_name.machine}'


global cpu
global gpu
global mem

threads: list[Thread] = []

for fn in [
	lambda: globals().update({'gpu': get_gpu()}), 
	lambda: globals().update({'cpu': get_cpu()}),
 	lambda: globals().update({'mem': get_mem()}),
]:
	t: Thread = Thread(target=fn)
	t.start()
	threads.append(t)

for t in threads: t.join()

print(cpu, gpu, mem, get_uname())
