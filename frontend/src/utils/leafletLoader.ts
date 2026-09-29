/**
 * Leaflet Dynamic Script & Style Loader
 * 
 * Dynamically loads Leaflet.js and its stylesheet from CDN if not already present.
 * Ensures the interactive map works seamlessly even without a Google Maps API key.
 */

let leafletPromise: Promise<any> | null = null;

export function isLeafletLoaded(): boolean {
  return typeof window !== 'undefined' && !!(window as any).L;
}

export function loadLeafletScript(): Promise<any> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Leaflet cannot be loaded in server environment'));
  }

  if (isLeafletLoaded()) {
    return Promise.resolve((window as any).L);
  }

  if (leafletPromise) {
    return leafletPromise;
  }

  leafletPromise = new Promise((resolve, reject) => {
    // 1. Inject Leaflet CSS if not already injected
    const existingCss = document.querySelector('link[data-leaflet-css="true"]');
    if (!existingCss) {
      const link = document.createElement('link');
      link.rel = 'stylesheet';
      link.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
      link.integrity = 'sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=';
      link.crossOrigin = '';
      link.setAttribute('data-leaflet-css', 'true');
      document.head.appendChild(link);
    }

    // 2. Inject Leaflet JS script
    const existingScript = document.querySelector('script[data-leaflet-js="true"]');
    if (existingScript) {
      if (isLeafletLoaded()) {
        resolve((window as any).L);
      } else {
        existingScript.addEventListener('load', () => resolve((window as any).L));
        existingScript.addEventListener('error', () => reject(new Error('LEAFLET_LOAD_ERROR')));
      }
      return;
    }

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
    script.integrity = 'sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=';
    script.crossOrigin = '';
    script.async = true;
    script.setAttribute('data-leaflet-js', 'true');

    script.onload = () => {
      if (isLeafletLoaded()) {
        resolve((window as any).L);
      } else {
        setTimeout(() => {
          if (isLeafletLoaded()) {
            resolve((window as any).L);
          } else {
            reject(new Error('LEAFLET_INIT_FAILED'));
          }
        }, 100);
      }
    };

    script.onerror = () => {
      leafletPromise = null;
      reject(new Error('LEAFLET_LOAD_ERROR'));
    };

    document.head.appendChild(script);
  });

  return leafletPromise;
}
