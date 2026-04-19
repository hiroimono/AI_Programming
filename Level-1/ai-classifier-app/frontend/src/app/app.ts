import { Component } from '@angular/core';
import { ClassifierComponent } from './classifier/classifier.component';

@Component({
  selector: 'app-root',
  imports: [ClassifierComponent],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {}
