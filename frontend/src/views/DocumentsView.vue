<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Plus, Delete, Refresh } from '@element-plus/icons-vue'
import { useDocumentsStore } from '@/stores/documents'

const docs = useDocumentsStore()
const dialogVisible = ref(false)
const uploadTitle = ref('')
const uploadFile = ref<File | null>(null)

onMounted(() => docs.load())

function handleFile(f: File | undefined) {
  uploadFile.value = f ?? null
}

async function doUpload() {
  if (!uploadFile.value) { ElMessage.warning('请选择文件'); return }
  try {
    await docs.upload(uploadFile.value, uploadTitle.value || null)
    ElMessage.success('上传成功 — 已解析并向量化')
    dialogVisible.value = false
    uploadFile.value = null
    uploadTitle.value = ''
  } catch (e: unknown) {
    ElMessage.error((e as Error).message || '上传失败')
  }
}

async function onRemove(id: string, filename: string) {
  try {
    await ElMessageBox.confirm(`确定删除《${filename}》？关联的分块和向量也会一起删除。`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await docs.remove(id)
    ElMessage.success('已删除')
  } catch {}
}

const parseStatusLabel: Record<string, string> = {
  pending: '排队中',
  parsing: '解析中',
  done: '完成',
  error: '失败',
  existing: '已存在',
}
const parseStatusType: Record<string, string> = {
  done: 'success', error: 'danger', existing: 'info',
}
</script>

<template>
  <div class="docs-view">
    <header class="docs-header">
      <div class="title">📚 知识库管理</div>
      <div class="actions">
        <el-button :icon="Refresh" plain @click="docs.load()">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="dialogVisible = true">上传文档</el-button>
      </div>
    </header>

    <div class="docs-content">
      <el-table :data="docs.items" v-loading="docs.loading" stripe style="width:100%">
        <el-table-column prop="filename" label="文件名" min-width="220" />
        <el-table-column prop="file_type" label="格式" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.file_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="parseStatusType[row.parse_status] ?? 'info'" size="small">
              {{ parseStatusLabel[row.parse_status] ?? row.parse_status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="chunk_count" label="分块数" width="90" />
        <el-table-column prop="title" label="标题" min-width="160">
          <template #default="{ row }">{{ row.title || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button
              link type="danger" :icon="Delete"
              @click="onRemove(row.id, row.filename)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!docs.loading && docs.items.length === 0" description="还没有上传任何文档" />
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="dialogVisible" title="上传文档" width="480px">
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".pdf,.docx,.md,.markdown,.txt"
        :on-change="(f: any) => handleFile(f.raw)"
      >
        <el-icon class="el-icon--upload"><Upload /></el-icon>
        <div class="el-upload__text">拖拽到这里，或 <em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">支持 PDF / Word / Markdown / TXT，上传后自动解析 + 分块 + 向量化</div>
        </template>
      </el-upload>

      <el-form :model="{ title: uploadTitle }" label-width="60px" style="margin-top:12px">
        <el-form-item label="标题">
          <el-input v-model="uploadTitle" placeholder="可选，留空用文件名" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="docs.uploading" @click="doUpload">开始上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.docs-view { display: flex; flex-direction: column; height: 100%; }
.docs-header {
  padding: 14px 24px; background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex; justify-content: space-between; align-items: center;
}
.docs-header .title { font-size: 16px; font-weight: 600; }
.docs-content { flex: 1; padding: 20px; overflow: auto; }
</style>
