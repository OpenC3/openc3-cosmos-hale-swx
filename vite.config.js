import { defineConfig } from 'vite'
import VitePluginStyleInject from 'vite-plugin-style-inject'
import vue from '@vitejs/plugin-vue'

const DEFAULT_EXTENSIONS = ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json']

export default defineConfig({
  // public/ belongs to the gem (the store image), not to this build -- without
  // this Vite would copy it into the widget output directory.
  publicDir: false,
  build: {
    // Inline the logo as a data URI (default limit is 4096, the PNG is ~7KB).
    // The built widget is a single .umd.min.js served from the widgets bucket,
    // so a sibling asset file would have no URL to be fetched from.
    assetsInlineLimit: 16384,
    // WidgetModel builds this path from 'WIDGET HALESWX' in plugin.txt:
    // tools/widgets/HaleswxWidget/HaleswxWidget.umd.min.js
    outDir: 'tools/widgets/HaleswxWidget',
    emptyOutDir: true,
    sourcemap: true,
    lib: {
      entry: './src/HaleswxWidget.vue',
      name: 'HaleswxWidget',
      fileName: (format, entryName) => `${entryName}.${format}.min.js`,
      formats: ['umd'],
    },
    rollupOptions: {
      external: ['single-spa', 'vue', 'pinia', 'vue-router', 'vuetify'],
    },
  },
  plugins: [vue(), VitePluginStyleInject()],
  resolve: {
    extensions: [...DEFAULT_EXTENSIONS, '.vue'],
  },
})
