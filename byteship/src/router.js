import { createRouter, createWebHistory } from 'vue-router';
import FileUploadComponent from './components/FileUploadComponent.vue';
import FileDisplayComponent from './components/FileDisplayComponent.vue';

const routes = [
  {
    path: '/',
    component: FileUploadComponent
  },
  {
    path: '/file-display',
    name: 'FileDisplay',
    component: FileDisplayComponent,
    props: true
  }
];

const router = createRouter({
  history: createWebHistory(),
  routes
});

export default router;
