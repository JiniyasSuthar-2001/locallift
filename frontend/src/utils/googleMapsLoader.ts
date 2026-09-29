/**
 * Google Maps JavaScript API Singleton Loader
 * 
 * Safely loads the Google Maps JavaScript API script once per browser session.
 * Prevents multiple script injections, handles missing keys, network errors,
 * and script load failures cleanly.
 */

let loadPromise: Promise<void> | null = null;

interface LoaderOptions {
  apiKey?: string;
  libraries?: string[];
  version?: string;
}

export function isGoogleMapsLoaded(): boolean {
  return typeof window !== 'undefined' && !!(window as any).google?.maps;
}

export function loadGoogleMapsScript(options?: LoaderOptions): Promise<void> {
  if (typeof window === 'undefined') {
    return Promise.reject(new Error('Google Maps cannot be loaded in server environment'));
  }

  // If already loaded globally on window
  if (isGoogleMapsLoaded()) {
    return Promise.resolve();
  }

  // If already loading, return existing promise
  if (loadPromise) {
    return loadPromise;
  }

  const apiKey = (options?.apiKey || import.meta.env.VITE_GOOGLE_MAPS_API_KEY || '').trim();
  if (!apiKey) {
    return Promise.reject(new Error('MISSING_KEY'));
  }

  loadPromise = new Promise<void>((resolve, reject) => {
    // Check if script element already exists in document
    const existingScript = document.querySelector('script[data-gmaps-loader="true"]');
    if (existingScript) {
      if (isGoogleMapsLoaded()) {
        resolve();
      } else {
        existingScript.addEventListener('load', () => resolve());
        existingScript.addEventListener('error', () => reject(new Error('LOAD_ERROR')));
      }
      return;
    }

    const libraries = options?.libraries?.join(',') || 'places,geometry';
    const version = options?.version || 'weekly';

    const script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=${libraries}&v=${version}&loading=async`;
    script.async = true;
    script.defer = true;
    script.setAttribute('data-gmaps-loader', 'true');

    script.onload = () => {
      if (isGoogleMapsLoaded()) {
        resolve();
      } else {
        // Give short grace period for async initialization
        setTimeout(() => {
          if (isGoogleMapsLoaded()) {
            resolve();
          } else {
            reject(new Error('INITIALIZATION_FAILED'));
          }
        }, 100);
      }
    };

    script.onerror = (err) => {
      loadPromise = null;
      script.remove();
      reject(new Error('SCRIPT_LOAD_ERROR'));
    };

    document.head.appendChild(script);
  });

  return loadPromise;
}
