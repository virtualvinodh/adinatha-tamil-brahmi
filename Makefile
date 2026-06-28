.PHONY: font features pocketbase pocketbase-setup jinavani-dev

font:
	fontmake -u Adinatha-Tamil-Brahmi-2.ufo -o ttf --keep-overlaps

features:
	python3 gen_features.py && fontmake -u Adinatha-Tamil-Brahmi-2.ufo -o ttf --keep-overlaps

pocketbase-setup:
	bash ./backend/setup.sh

pocketbase:
	./backend/pocketbase serve --http="127.0.0.1:8090" --dir="./backend/pb_data"

jinavani-dev:
	cd /mnt/c/Users/vinod/Projects/jinavani && npx quasar dev
