import {ChangeDetectionStrategy, Component, signal, inject, Input, Output, EventEmitter} from '@angular/core';

// --- PACKAGE DETAIL COMPONENT ---

@Component({
  selector: 'app-package-detail',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 animate-fade-in">
      <!-- Back Button -->
      <button (click)="close.emit()" class="mb-6 bg-gray-700 hover:bg-gray-600 text-gray-200 px-4 py-2 rounded-lg transition-colors flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="12" x2="5" y2="12"></line><polyline points="12 19 5 12 12 5"></polyline></svg>
        Back to Search
      </button>

      <!-- Header -->
      <div class="flex flex-col sm:flex-row justify-between items-start gap-4 mb-4">
        <div>
            <h2 class="text-3xl font-bold" [class.text-red-500]="!package.package_exists" [class.text-blue-400]="package.package_exists">
                {{ package.name }}
                @if (!package.package_exists) {
                    <span class="text-sm align-middle">(Package not found on PyPI)</span>
                }
            </h2>
            <p class="text-gray-400 mt-1">{{ package.summary }}</p>
        </div>
        <span class="text-sm font-mono bg-gray-700 text-yellow-300 px-3 py-1 rounded-md flex-shrink-0">{{ package.version }}</span>
      </div>

      <p class="text-gray-300 mb-6">{{ package.description }}</p>

      <!-- Metadata Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-gray-700 pt-6">
        <div>
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Details</h3>
          <dl class="space-y-2 text-sm">
            @if(package.author){
              <div class="grid grid-cols-3 gap-1"><dt class="text-gray-500">Author</dt><dd class="col-span-2 text-gray-300">{{package.author}}</dd></div>
            }
            @if(package.license){
              <div class="grid grid-cols-3 gap-1"><dt class="text-gray-500">License</dt><dd class="col-span-2 text-gray-300">{{package.license}}</dd></div>
            }
            @if(package.requires_python){
                <div class="grid grid-cols-3 gap-1"><dt class="text-gray-500">Requires</dt><dd class="col-span-2 text-gray-300">Python {{package.requires_python}}</dd></div>
            }
          </dl>
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Links</h3>
          <div class="flex flex-col space-y-2 text-sm">
            @if(package.home_page){
              <a [href]="package.home_page" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:underline">Homepage</a>
            }
            @if(package.package_url){
              <a [href]="package.package_url" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:underline">PyPI Package URL</a>
            }
             @if(package.project_urls?.['Documentation']){
              <a [href]="package.project_urls?.['Documentation']" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:underline">Documentation</a>
            }
          </div>
        </div>
      </div>

      <!-- Keywords -->
      @if(splitKeywords(package.keywords).length > 0){
        <div class="mt-6 pt-6 border-t border-gray-700">
            <h3 class="text-lg font-semibold text-gray-200 mb-3">Keywords</h3>
            <div class="flex flex-wrap gap-2">
                @for(keyword of splitKeywords(package.keywords); track $index){
                    <span class="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded-full">{{keyword}}</span>
                }
            </div>
        </div>
      }

      <!-- README Generation Stub -->
      <div class="mt-6 pt-6 border-t border-gray-700">
        <h3 class="text-lg font-semibold text-gray-200 mb-3">Generate README</h3>
        <p class="text-gray-400 text-sm mb-4">Click the button below to generate a README.md file for this package using an AI model.</p>
        <button (click)="onGenerateReadme()" class="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
          Generate README.md
        </button>
        <!-- Generated README will be displayed here -->
      </div>
    </div>
  `,
  styles: [`
    .animate-fade-in {
      animation: fadeIn 0.5s ease-in-out;
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
  `]
})
export class PackageDetailComponent {
  @Input({ required: true }) package!: SearchResult;
  @Output() close = new EventEmitter<void>();

  /**
   * Placeholder for the README generation API call.
   */
  onGenerateReadme(): void {
    console.log(`TODO: Implement API call to generate README for ${this.package.name}`);
    console.log('README generation feature is not yet implemented.');
  }

  /**
   * Utility to split keywords for display.
   */
  splitKeywords(keywords: string | null | undefined): string[] {
    if (!keywords) return [];
    return keywords.split(/, | |,\s*/).map(k => k.trim()).filter(Boolean);
  }
}
