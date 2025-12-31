import FileText from '@lucide/svelte/icons/file-text';
import FileCode from '@lucide/svelte/icons/file-code';
import FileJson from '@lucide/svelte/icons/file-json';
import FileType from '@lucide/svelte/icons/file-type';
import FileImage from '@lucide/svelte/icons/file-image';
import FileVideo from '@lucide/svelte/icons/file-video';
import FileAudio from '@lucide/svelte/icons/file-audio';
import FileArchive from '@lucide/svelte/icons/file-archive';
import Terminal from '@lucide/svelte/icons/terminal';
import type { ComponentType } from 'svelte';

/**
 * Get the appropriate Lucide icon for a given filename based on its extension.
 */
export function getFileIcon(filename: string): ComponentType {
  const ext = filename.split('.').pop()?.toLowerCase();
  
  if (!ext) return FileText;

  switch (ext) {
    // Markdown & Text
    case 'md':
    case 'markdown':
    case 'txt':
      return FileText;
    
    // Code
    case 'js':
    case 'ts':
    case 'jsx':
    case 'tsx':
    case 'py':
    case 'rb':
    case 'go':
    case 'rs':
    case 'c':
    case 'cpp':
    case 'h':
    case 'hpp':
    case 'java':
    case 'kt':
    case 'swift':
    case 'php':
    case 'sh':
    case 'bash':
    case 'zsh':
      return FileCode;
    
    // Web / Data
    case 'html':
    case 'htm':
    case 'xml':
    case 'rss':
      return FileType;
    case 'json':
      return FileJson;
    case 'yaml':
    case 'yml':
    case 'toml':
      return FileType;
    case 'css':
    case 'scss':
    case 'less':
      return FileType;
    
    // Images
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
    case 'webp':
    case 'bmp':
    case 'ico':
      return FileImage;
    
    // Video
    case 'mp4':
    case 'mov':
    case 'avi':
    case 'mkv':
    case 'webm':
      return FileVideo;
    
    // Audio
    case 'mp3':
    case 'wav':
    case 'ogg':
    case 'flac':
    case 'm4a':
      return FileAudio;
    
    // Archives
    case 'zip':
    case 'tar':
    case 'gz':
    case '7z':
    case 'rar':
      return FileArchive;

    // Config / Scripts
    case 'env':
    case 'lock':
    case 'gitignore':
    case 'dockerfile':
      return Terminal;

    default:
      return FileText;
  }
}

