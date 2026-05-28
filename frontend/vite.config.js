import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import fs from 'fs'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const questionDataDir = path.resolve(__dirname, '..', 'QuestionData')
const publicDataDir = path.resolve(__dirname, 'public', 'data')

function serveQuestionData() {
  return {
    name: 'serve-question-data',
    configureServer(server) {
      server.middlewares.use('/QuestionData', (req, res) => {
        const filePath = path.join(questionDataDir, req.url)
        if (fs.existsSync(filePath)) {
          const ext = path.extname(filePath)
          const mime = { '.pdf': 'application/pdf', '.png': 'image/png', '.json': 'application/json' }
          res.setHeader('Content-Type', mime[ext] || 'application/octet-stream')
          fs.createReadStream(filePath).pipe(res)
        } else {
          res.statusCode = 404
          res.end()
        }
      })
      server.middlewares.use('/data', (req, res) => {
        const filePath = path.join(publicDataDir, req.url)
        if (fs.existsSync(filePath)) {
          fs.createReadStream(filePath).pipe(res)
        } else {
          res.statusCode = 404
          res.end()
        }
      })
    },
  }
}

export default defineConfig(({ mode }) => ({
  plugins: [vue(), serveQuestionData()],
  base: mode === 'production' ? '/Yamaguchi-EMaT/' : '/',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    target: 'es2022',
  },
  optimizeDeps: {
    include: ['pdfjs-dist'],
  },
}))
