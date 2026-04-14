import { defineConfig } from 'vitest/config'
import path from 'path'

export default defineConfig({
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, 'src/shared'),
    },
  },
  test: {
    projects: [
      {
        resolve: {
          alias: {
            '@shared': path.resolve(__dirname, 'src/shared'),
          },
        },
        test: {
          name: 'main',
          include: ['tests/main/**/*.test.ts'],
          environment: 'node',
        },
      },
      {
        resolve: {
          alias: {
            '@shared': path.resolve(__dirname, 'src/shared'),
          },
        },
        test: {
          name: 'renderer',
          include: ['tests/renderer/**/*.test.tsx'],
          environment: 'jsdom',
          setupFiles: ['tests/renderer/setup.ts'],
        },
      },
    ],
  },
})
