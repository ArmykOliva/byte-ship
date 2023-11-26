<template>
    <div>
      <input type="file" @change="handleFileUpload" />
    </div>
  </template>
  
  <script>
  export default {
  methods: {
    handleFileUpload(event) {
      const file = event.target.files[0];
      const reader = new FileReader();

      reader.onload = (e) => {
        localStorage.setItem('uploadedFile', e.target.result);
        this.$router.push({ name: 'FileDisplay' });
      };

      reader.readAsText(file);
    }
  }
}


  </script>
  