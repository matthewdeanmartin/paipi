import {
  ChangeDetectionStrategy,
  Component,
  computed,
  EventEmitter,
  inject,
  Input,
  OnInit,
  Output, // <-- Import Output
  signal
} from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'app-package-detail',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './package_page.html', // We'll use a separate template file for clarity
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
// Implement the OnInit interface
export class PackageDetailComponent implements OnInit {
  @Input({ required: true }) package!: SearchResult;
  @Output() close = new EventEmitter<void>();
  // --- NEW: Event emitter to notify the parent component ---
  @Output() readmeGenerated = new EventEmitter<string>();

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

  // --- NEW: ngOnInit Lifecycle Hook ---
  ngOnInit(): void {
    console.log(`[PackageDetail] ngOnInit for '${this.package.name}'. Checking live availability from server...`);
    this.checkAndLoadCachedReadme();
  }

  async checkAndLoadCachedReadme(): Promise<void> {
    this.readmeIsLoading.set(true);
    this.readmeError.set(null);
    this.readmeContent.set(null);

    try {
      const availabilityUrl = `${this.apiUrl}/availability?name=${encodeURIComponent(this.package.name)}`;
      console.log(`[PackageDetail] Checking availability at: ${availabilityUrl}`);
      const availability = await firstValueFrom(this.http.get<AvailabilityResponse>(availabilityUrl));

      if (availability.readme_cached) {
        console.log(`[PackageDetail] README is cached on server. Fetching content...`);
        const readmeUrl = `${this.apiUrl}/readme/by-name/${encodeURIComponent(this.package.name)}`;
        const markdown = await firstValueFrom(this.http.get(readmeUrl, { responseType: 'text' }));
        this.readmeContent.set(markdown);
      } else {
        console.log(`[PackageDetail] README is not cached on server. Waiting for user to generate.`);
      }
    } catch (err: any) {
      console.error("Failed to check/load cached README:", err);
      this.readmeError.set(err.error?.detail || err.message || 'Could not check for cached README.');
    } finally {
      this.readmeIsLoading.set(false);
    }
  }

  async onGenerateReadme(): Promise<void> {
    // --- NEW: Add logging for debugging ---
    console.log(`[PackageDetail] Generating new README for '${this.package.name}'...`);

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
      const markdown = await firstValueFrom(this.http.post(`${this.apiUrl}/readme`, payload, { responseType: 'text' }));
      this.readmeContent.set(markdown);

      // --- NEW: Emit event to parent on success ---
      console.log(`[PackageDetail] Emitting readmeGenerated event for '${this.package.name}'`);
      this.readmeGenerated.emit(this.package.name);

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
      metadata: { ...this.package }
    };

    try {
      const blob = await firstValueFrom(this.http.post(`${this.apiUrl}/generate_package`, payload, { responseType: 'blob' }));
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
