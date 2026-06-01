const CACHE_NAME = 'monitor-aesa-v5'; 
const ASSETS_TO_CACHE = [
  './',
  './index.html',
  './style.css',
  './iso.png',  
  './Aesa.png'
];



// Instalar y guardar los archivos visuales en caché
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(ASSETS_TO_CACHE);
      })
  );
});

// Interceptar las peticiones de red
self.addEventListener('fetch', event => {
  // NUNCA cachear el JSON de datos, siempre ir a buscar el nuevo
  if (event.request.url.includes('datos_red.json')) {
    event.respondWith(fetch(event.request));
    return;
  }

  // Para el resto (HTML, CSS, Imagen), buscar primero en caché
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        return response || fetch(event.request);
      })
  );
});