// gl-photos.js: choose, shrink and upload repair photos (Components/PhotoPicker calls it; server side: Photos.py).
//   GLPhotos.pick(max)        -> Promise<{photos: [{blob, preview, type, size, width, height}], skipped: n}>
//   GLPhotos.put(url, blob)   -> Promise<{ok, error?, sha256?}>  (PUT to the signed Cloudflare Worker link)
//   GLPhotos.revoke(preview)  frees a preview address
// Photos are redrawn on a canvas (longest side 2000 px, JPEG): smaller uploads, and the camera's hidden data
// (GPS location, phone model) is left behind.
(function () {
  var MAX_SIDE = 2000, MAX_BYTES = 3.8 * 1024 * 1024;

  function load(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file), img = new Image();
      img.onload = function () { resolve({ img: img, url: url }); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error('unreadable')); };
      img.src = url;  // browsers apply the photo's EXIF rotation when drawing it
    });
  }

  function toBlob(canvas, quality) {
    return new Promise(function (resolve) { canvas.toBlob(resolve, 'image/jpeg', quality); });
  }

  function shrink(file) {
    return load(file).then(function (o) {
      var w = o.img.naturalWidth, h = o.img.naturalHeight, k = Math.min(1, MAX_SIDE / Math.max(w, h, 1));
      var c = document.createElement('canvas');
      c.width = Math.max(1, Math.round(w * k)); c.height = Math.max(1, Math.round(h * k));
      var g = c.getContext('2d');
      g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);  // transparent PNGs get a white background
      g.drawImage(o.img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(o.url);
      return toBlob(c, 0.85).then(function (b) { return b && b.size > MAX_BYTES ? toBlob(c, 0.7) : b; })
        .then(function (b) {
          if (!b) throw new Error('unreadable');
          return { blob: b, preview: URL.createObjectURL(b), type: 'image/jpeg', size: b.size, width: c.width, height: c.height };
        });
    });
  }

  window.GLPhotos = {
    pick: function (max) {
      return new Promise(function (resolve) {
        var input = document.createElement('input'), done = false;
        input.type = 'file'; input.accept = 'image/*'; input.multiple = max > 1;
        input.style.position = 'fixed'; input.style.left = '-9999px';
        document.body.appendChild(input);
        function finish(list) { if (done) return; done = true; input.remove(); resolve(list); }
        input.addEventListener('cancel', function () { finish({ photos: [], skipped: 0 }); });
        function handle(list) {
          var files = Array.prototype.slice.call(list || []).filter(function (f) { return /^image\//.test(f.type) || /\.(jpe?g|png|webp|heic|heif)$/i.test(f.name); }).slice(0, max);
          var out = [], bad = 0;
          files.reduce(function (p, f) {
            return p.then(function () { return shrink(f).then(function (x) { out.push(x); }, function () { bad++; }); });
          }, Promise.resolve()).then(function () { finish({ photos: out, skipped: bad }); });
        }
        input.addEventListener('change', function () { handle(input.files); });
        if (window.GLPhotos.testFiles) {  // UI tests: files made in the page instead of the system file picker
          var t = window.GLPhotos.testFiles; window.GLPhotos.testFiles = null; handle(t); return;
        }
        input.click();
      });
    },
    put: function (url, blob) {
      return fetch(url, { method: 'PUT', body: blob, headers: { 'Content-Type': blob.type || 'image/jpeg' } })
        .then(function (r) { return r.json().catch(function () { return { ok: false, error: 'The photo upload failed (' + r.status + ').' }; }); })
        .catch(function () { return { ok: false, error: 'The photo upload didn\'t get through. Check your connection and try again.' }; });
    },
    revoke: function (preview) { try { URL.revokeObjectURL(preview); } catch (e) { /* ignore */ } },
  };
})();
