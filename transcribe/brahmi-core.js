const KEY   = 'brahmi_v4';
const TOTAL = 43;

function imgSrc(n) {
  return n === 1 ? 'images/img01.png' : `images/img${String(n).padStart(2,'0')}.jpeg`;
}

function ld() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } }

function renderCrop(c, canvas, img) {
  const W=img.naturalWidth, H=img.naturalHeight;
  const cw=Math.round(c.fw*W), ch=Math.round(c.fh*H);
  const rot=(c.rot||0), flipped=rot===90||rot===270;
  const outW=flipped?ch:cw, outH=flipped?cw:ch;
  canvas.width=outW; canvas.height=outH;
  const tctx=canvas.getContext('2d');
  tctx.save(); tctx.translate(outW/2,outH/2); tctx.rotate(rot*Math.PI/180);
  tctx.drawImage(img, c.fx*W, c.fy*H, cw, ch, -cw/2, -ch/2, cw, ch);
  tctx.restore();
}

function renderLineCanvas(cropCv, line, lineCanvas) {
  if (!cropCv.width) return;
  const ch=cropCv.height, cw=cropCv.width;
  const ly=Math.round(line.fy*ch);
  const lh=Math.max(1,Math.round(line.fh*ch));
  const rot=(line.rot||0)*Math.PI/180;
  const sw=rot%Math.PI?lh:cw, sh=rot%Math.PI?cw:lh;
  lineCanvas.width=sw; lineCanvas.height=sh;
  const lctx=lineCanvas.getContext('2d');
  lctx.save(); lctx.translate(sw/2,sh/2); lctx.rotate(rot);
  lctx.drawImage(cropCv, 0,ly,cw,lh, -cw/2,-lh/2,cw,lh);
  lctx.restore();
}

// Per-page uploaded images, stored in IndexedDB (no localStorage size limit)
const ImageDB = {
  _db: null,
  async open() {
    if (this._db) return;
    await new Promise((res, rej) => {
      const r = indexedDB.open('brahmi_images', 1);
      r.onupgradeneeded = e => e.target.result.createObjectStore('imgs');
      r.onsuccess = e => { this._db = e.target.result; res(); };
      r.onerror = rej;
    });
  },
  async get(n) {
    await this.open();
    return new Promise(res => {
      this._db.transaction('imgs').objectStore('imgs').get(n).onsuccess = e => res(e.target.result || null);
    });
  },
  async put(n, dataUrl) {
    await this.open();
    return new Promise(res => {
      const tx = this._db.transaction('imgs','readwrite');
      tx.objectStore('imgs').put(dataUrl, n).onsuccess = res;
    });
  },
  async del(n) {
    await this.open();
    return new Promise(res => {
      const tx = this._db.transaction('imgs','readwrite');
      tx.objectStore('imgs').delete(n).onsuccess = res;
    });
  },

  // Load an image for page n: IDB first, then disk path fallback
  async loadImg(n, imgEl) {
    const stored = await this.get(n);
    imgEl.src = stored || imgSrc(n);
  }
};
