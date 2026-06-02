import 'dart:io';
import 'dart:convert';
import 'package:args/args.dart';

void main(List<String> arguments) async {
  final parser = ArgParser()
    ..addOption('input', abbr: 'i', help: 'Input markdown file path')
    ..addOption(
      'type',
      abbr: 't',
      help: 'Filter by prompt type (e.g. VFX, Image)',
    );

  final argResults = parser.parse(arguments);

  if (!argResults.wasParsed('input')) {
    print('Error: --input argument is required');
    print(parser.usage);
    exit(1);
  }

  final inputPath = argResults['input'];
  final filterType = argResults['type'];

  final file = File(inputPath);
  if (!await file.exists()) {
    print('Error: Input file not found at $inputPath');
    exit(1);
  }

  final content = await file.readAsString();
  final lines = content.split('\n');

  String? currentName;
  List<String> currentPromptLines = [];
  bool inPromptBlock = false;

  final prompts = <Map<String, String>>[];

  for (var i = 0; i < lines.length; i++) {
    final line = lines[i].trim();

    if (line.startsWith('#### ')) {
      currentName = line.substring(5).trim();
      continue;
    }

    if (line.startsWith('```')) {
      if (inPromptBlock) {
        // End of block
        inPromptBlock = false;
        if (currentName != null && currentPromptLines.isNotEmpty) {
          final promptText = currentPromptLines.join(' ');
          String type = 'Image';
          if (promptText.contains('VFX Prompt:'))
            type = 'VFX';
          else if (promptText.contains('Music Prompt:'))
            type = 'Audio';
          else if (promptText.contains('SFX Prompt:'))
            type = 'Audio';

          if (promptText.contains('Prompt:')) {
            prompts.add({
              'name': currentName,
              'prompt': promptText
                  .replaceAll(RegExp(r'(VFX |Music |SFX )?Prompt:'), '')
                  .trim(),
              'type': type,
            });
          }
          currentPromptLines = [];
        }
      } else {
        // Start of block
        inPromptBlock = true;
      }
      continue;
    }

    if (inPromptBlock) {
      if (line.isNotEmpty) {
        currentPromptLines.add(line);
      }
    }
  }

  // Filter
  final filtered = filterType != null
      ? prompts.where((p) => p['type'] == filterType).toList()
      : prompts;

  print(jsonEncode(filtered));
}
