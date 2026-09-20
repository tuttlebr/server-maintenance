SHELL := /bin/bash

.DEFAULT_GOAL := start

ifneq ($(origin FLEET_SSH_DIR), undefined)
export FLEET_SSH_DIR
endif
ifneq ($(origin FLEET_SSH_KEY_PATH), undefined)
export FLEET_SSH_KEY_PATH
endif
ifneq ($(origin FLEET_HOSTS_CSV), undefined)
export FLEET_HOSTS_CSV
endif
ifneq ($(origin FLEET_START_TIMEOUT_SECONDS), undefined)
export FLEET_START_TIMEOUT_SECONDS
endif

.PHONY: start prepare enroll-hosts status

start:
	@./scripts/start.sh start

prepare:
	@./scripts/start.sh prepare

enroll-hosts:
	@./scripts/start.sh enroll-hosts

status:
	@./scripts/start.sh status
