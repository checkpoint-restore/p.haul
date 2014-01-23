all: rpc_pb2.py stats_pb2.py

.PHONY: all

rpc_pb2.py: rpc.proto
	protoc --proto_path=. --python_out=. rpc.proto

stats_pb2.py: stats.proto
	protoc --proto_path=. --python_out=. stats.proto
