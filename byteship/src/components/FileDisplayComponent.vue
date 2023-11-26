<template>
    <div v-if="fileContent">
      <p>{{ fileContent }}</p>
    </div>
    <div v-else>
      <p>No file content to display.</p>
    </div>
  </template>
  
  <script>
  export default {
  data() {
    return {
      fileContent: ''
    };
  },
  mounted() {
    this.fileContent = localStorage.getItem('uploadedFile');
  }
}

  </script>
  
