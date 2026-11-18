.PHONY: help run diagnose deb install test clean

help:
	@echo "make run       启动网页界面（自动开浏览器）"
	@echo "make diagnose  命令行诊断"
	@echo "make test      语法检查 + 冒烟测试"
	@echo "make deb       构建 .deb 到 dist/"
	@echo "make install   源码安装到 /usr/local（需要 sudo）"
	@echo "make clean     清理构建产物"

run:
	python3 -m steam_node_doctor serve --open

diagnose:
	python3 -m steam_node_doctor diagnose

test:
	python3 -m compileall -q steam-node-doctor
	python3 -m steam_node_doctor --version
	@echo "OK"

deb:
	bash packaging/build-deb.sh

install:
	sudo bash install.sh

clean:
	rm -rf dist build *.egg-info
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
