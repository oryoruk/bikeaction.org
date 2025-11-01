import { Injectable } from '@angular/core';
import { version, buildDate, commitHash } from 'src/environments/version';

@Injectable({
  providedIn: 'root',
})
export class VersionService {
  getBuildDate(): string {
    return buildDate;
  }
  getVersion(): string {
    return `Version ${version}, commit ${commitHash}, built at ${buildDate}`;
  }
}
