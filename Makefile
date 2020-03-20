
all: progress2span.beam

# Generate JSON files from .csv progress traces
%.json: progress2span.beam %.csv
	escript $^ $@ -tu

#
# To upload spans, post them to http://127.0.0.1:9411/api/v2/spans
# with Content-Type: application/json
#
%.upload: %.json
	curl -v -H 'Content-Type: application/json' \
	    http://127.0.0.1:9411/api/v2/spans -d @- < $<

# Compile the Erlang script
%.beam: %.erl
	erlc $<

clean:
	rm -f *.beam

distclean: clean
	rm -f zipkin.*
	cd demo && $(MAKE) -k clean || true


#
# Zipkin related convenience targets
#
CWD = $(shell pwd)

## Start a local copy of Zipkin
zipkin: zipkin.jar
	cd /tmp && java -jar $(CWD)/zipkin.jar

## Seems unsafe? It's what the kids do these days...
zipkin.jar:
	curl https://zipkin.io/quickstart.sh | bash -s

## Or just run it in docker
zipkin.docker:
	docker run -d -p 9411:9411 openzipkin/zipkin

jaeger.docker:
	docker run -d --name jaeger \
	-e COLLECTOR_ZIPKIN_HTTP_PORT=9411 \
	-p 5775:5775/udp \
	-p 6831:6831/udp \
	-p 6832:6832/udp \
	-p 5778:5778 \
	-p 16686:16686 \
	-p 14268:14268 \
	-p 14250:14250 \
	-p 9411:9411 \
	jaegertracing/all-in-one:1.17
