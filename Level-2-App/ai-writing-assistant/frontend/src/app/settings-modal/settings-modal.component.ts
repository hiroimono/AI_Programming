import { Component, signal, HostListener } from '@angular/core';
import { MatIconModule } from '@angular/material/icon';

export type SettingsModal = 'upgrade' | 'learn' | 'help' | null;

@Component({
  selector: 'app-settings-modal',
  imports: [MatIconModule],
  templateUrl: './settings-modal.component.html',
  styleUrl: './settings-modal.component.scss',
})
export class SettingsModalComponent {
  activeModal = signal<SettingsModal>(null);

  // FAQ state
  expandedFaq = signal<number | null>(null);

  faqItems = [
    {
      q: 'How does the AI Writing Assistant work?',
      a: 'Our AI analyzes your prompt and writing mode to generate high-quality content. It uses advanced language models to understand context, tone, and style requirements, delivering tailored output for blogs, emails, reports, and creative writing.',
    },
    {
      q: 'Can I edit the generated content?',
      a: 'Absolutely. All generated content is fully editable. You can copy, modify, regenerate, or use it as a starting point for your own writing. The AI is a tool to assist you — you always have full control.',
    },
    {
      q: 'Is my data private and secure?',
      a: 'Yes. We take privacy seriously. Your conversations are encrypted in transit and at rest. We do not use your data to train models. You can delete your chat history at any time.',
    },
    {
      q: 'What writing modes are available?',
      a: 'Currently we offer General, Blog Post, Email, Report, and Creative writing modes. Each mode adjusts the AI\'s tone, structure, and vocabulary to match the specific writing context.',
    },
    {
      q: 'How do I get the best results?',
      a: 'Be specific in your prompts. Include details about tone, audience, length, and key points. Use the appropriate writing mode. You can also regenerate or edit messages to refine the output.',
    },
    {
      q: 'What are the usage limits?',
      a: 'Free plan includes 50 messages per day. Pro plan offers unlimited messages with priority processing. Enterprise plans include team collaboration, custom models, and dedicated support.',
    },
  ];

  open(modal: SettingsModal) {
    this.activeModal.set(modal);
    this.expandedFaq.set(null);
  }

  close() {
    this.activeModal.set(null);
  }

  toggleFaq(index: number) {
    this.expandedFaq.update((current) => (current === index ? null : index));
  }

  @HostListener('document:keydown.escape')
  onEscape() {
    this.close();
  }
}
