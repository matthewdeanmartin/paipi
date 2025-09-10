import {ChangeDetectionStrategy, Component, computed, EventEmitter, inject, Input, Output, signal} from '@angular/core';
import {HttpClient, HttpErrorResponse} from '@angular/common/http';
import {DomSanitizer, SafeHtml} from '@angular/platform-browser';
import {firstValueFrom} from 'rxjs';

@Component({
  selector: 'app-package-detail',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 animate-fade-in">
      <!-- Back Button -->
      <button (click)="close.emit()"
              class="mb-6 bg-gray-700 hover:bg-gray-600 text-gray-200 px-4 py-2 rounded-lg transition-colors flex items-center gap-2">
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <line x1="19" y1="12" x2="5" y2="12"></line>
          <polyline points="12 19 5 12 12 5"></polyline>
        </svg>
        Back to Search
      </button>

      <!-- Header -->
      <div class="flex flex-col sm:flex-row justify-between items-start gap-4 mb-4">
        <div>
          <h2 class="text-3xl font-bold" [class.text-red-500]="!package.package_exists"
              [class.text-blue-400]="package.package_exists">
            {{ package.name }}
            @if (!package.package_exists) {
              <span class="text-sm align-middle">(Package not found on PyPI)</span>
            }
          </h2>
          <p class="text-gray-400 mt-1">{{ package.summary }}</p>
        </div>
        <span
          class="text-sm font-mono bg-gray-700 text-yellow-300 px-3 py-1 rounded-md flex-shrink-0">{{ package.version }}</span>
      </div>

      <p class="text-gray-300 mb-6">{{ package.description }}</p>

      <!-- Metadata Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6 border-t border-gray-700 pt-6">
        <div>
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Details</h3>
          <dl class="space-y-2 text-sm">
            @if (package.author) {
              <div class="grid grid-cols-3 gap-1">
                <dt class="text-gray-500">Author</dt>
                <dd class="col-span-2 text-gray-300">{{ package.author }}</dd>
              </div>
            }
            @if (package.license) {
              <div class="grid grid-cols-3 gap-1">
                <dt class="text-gray-500">License</dt>
                <dd class="col-span-2 text-gray-300">{{ package.license }}</dd>
              </div>
            }
            @if (package.requires_python) {
              <div class="grid grid-cols-3 gap-1">
                <dt class="text-gray-500">Requires</dt>
                <dd class="col-span-2 text-gray-300">Python {{ package.requires_python }}</dd>
              </div>
            }
          </dl>
        </div>
        <div>
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Links</h3>
          <div class="flex flex-col space-y-2 text-sm">
            @if (package.home_page) {
              <a [href]="package.home_page" target="_blank" rel="noopener noreferrer"
                 class="text-blue-400 hover:underline">Homepage</a>
            }
            @if (package.package_url) {
              <a [href]="package.package_url" target="_blank" rel="noopener noreferrer"
                 class="text-blue-400 hover:underline">PyPI Package URL</a>
            }
            @if (package.project_urls?.['Documentation']) {
              <a [href]="package.project_urls?.['Documentation']" target="_blank" rel="noopener noreferrer"
                 class="text-blue-400 hover:underline">Documentation</a>
            }
          </div>
        </div>
      </div>

      <!-- Keywords -->
      @if (splitKeywords(package.keywords).length > 0) {
        <div class="mt-6 pt-6 border-t border-gray-700">
          <h3 class="text-lg font-semibold text-gray-200 mb-3">Keywords</h3>
          <div class="flex flex-wrap gap-2">
            @for (keyword of splitKeywords(package.keywords); track $index) {
              <span class="text-xs bg-blue-900/50 text-blue-300 px-2 py-1 rounded-full">{{ keyword }}</span>
            }
          </div>
        </div>
      }

      <!-- README Generation -->
      <div class="mt-6 pt-6 border-t border-gray-700">
        <h3 class="text-lg font-semibold text-gray-200 mb-3">README.md</h3>

        @if (readmeIsLoading()) {
          <div class="flex items-center gap-3 text-gray-400 p-4 bg-gray-800 rounded-md">
            <svg class="animate-spin h-5 w-5 text-blue-400" xmlns="http://www.w3.org/2000/svg" fill="none"
                 viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span>Generating README with AI...</span>
          </div>
        } @else if (safeReadmeHtml()) {
          <div class="prose prose-sm prose-invert bg-gray-900/50 p-4 rounded-md border border-gray-600 max-w-none">
            <div [innerHTML]="safeReadmeHtml()"></div>
          </div>
          <div class="mt-6 flex gap-4">
            <button (click)="onDownloadPackage()" [disabled]="packageIsLoading()"
                    class="bg-green-600 hover:bg-green-500 text-white font-bold py-2 px-4 rounded-lg transition-colors flex items-center justify-center w-48 disabled:opacity-50 disabled:cursor-not-allowed">
              @if (packageIsLoading()) {
                <svg class="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              } @else {
                <span>Download Package</span>
              }
            </button>
            <button (click)="resetReadme()"
                    class="bg-gray-600 hover:bg-gray-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
              Regenerate
            </button>
          </div>
        } @else {
          <p class="text-gray-400 text-sm mb-4">Click the button below to generate a README.md file for this
            package.</p>
          <button (click)="onGenerateReadme()"
                  class="bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 px-4 rounded-lg transition-colors">
            Generate README.md
          </button>
          @if (readmeError()) {
            <p class="text-red-400 mt-2">{{ readmeError() }}</p>
          }
        }
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

  private http = inject(HttpClient);
  private sanitizer = inject(DomSanitizer);
  private readonly apiUrl = 'http://127.0.0.1:8080';

  readmeContent = signal<string | null>(null);
  readmeIsLoading = signal<boolean>(false);
  packageIsLoading = signal<boolean>(false);
  readmeError = signal<string | null>(null);

  safeReadmeHtml = computed<SafeHtml | null>(() => {
    const markdown = this.readmeContent();
    if (markdown && (window as any).marked) {
      const html = (window as any).marked.parse(markdown);
      return this.sanitizer.bypassSecurityTrustHtml(html);
    }
    return null;
  });

  async onGenerateReadme(): Promise<void> {
    this.readmeIsLoading.set(true);
    this.readmeError.set(null);
    this.readmeContent.set(null);

    const payload: ReadmeRequest = {
      name: this.package.name,
      summary: this.package.summary,
      description: this.package.description,
      license: this.package.license,
      homepage: this.package.home_page,
      documentation_url: this.package.project_urls?.['Documentation'],
      python_requires: this.package.requires_python,
    };

    try {
      const markdown = await firstValueFrom(this.http.post(`${this.apiUrl}/readme`, payload, {responseType: 'text'}));
      this.readmeContent.set(markdown);
    } catch (err: any) {
      console.error("README Generation Error:", err);
      this.readmeError.set(err.error?.detail || err.message || 'Failed to generate README.');
    } finally {
      this.readmeIsLoading.set(false);
    }
  }

  async onDownloadPackage(): Promise<void> {
    const markdown = this.readmeContent();
    if (!markdown) return;

    this.packageIsLoading.set(true);
    const payload: PackageGenerateRequest = {
      readme_markdown: markdown,
      metadata: {...this.package}
    };

    try {
      const blob = await firstValueFrom(this.http.post(`${this.apiUrl}/generate_package`, payload, {responseType: 'blob'}));
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${this.package.name.replace(/[^a-z0-9]/gi, '_')}.zip`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err) {
      if (err instanceof HttpErrorResponse && err.status === 501) {
        alert('The package generation feature is not yet implemented on the server.');
      } else {
        console.error("Package Download Error:", err);
        alert('An error occurred while trying to generate the package.');
      }
    } finally {
      this.packageIsLoading.set(false);
    }
  }

  resetReadme(): void {
    this.readmeContent.set(null);
    this.readmeError.set(null);
  }

  /**
   * Utility to split keywords for display.
   */
  splitKeywords(keywords: string | null | undefined): string[] {
    if (!keywords) return [];
    return keywords.split(/, | |,\s*/).map(k => k.trim()).filter(Boolean);
  }
}
